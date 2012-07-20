# coding: utf-8
# module info:
"""\
Talking Akinator event socket server

FreeSWITCH let us handle calls from this server.
Add this to {freeswitch}/conf/dialplan/default.xml:

  <extension name="akinator">
      <condition field="destination_number" expression="1313">
         <action application="socket" data="127.0.0.1:8888 async full"/>
      </condition>
  </extension>

It depends on tts_commandline to synthesize audio.
And pocketsphinx for speech recognition. Copy all files from grammar/
to {freeswitch}/grammar.

Enjoy!
"""

import sys
import random

from collections import defaultdict
from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.python import log
from xml.dom import minidom

from talkinator import akinator
from talkinator import eventsocket


class Grammar:
    # see grammar/akinator_gender.gram
    @classmethod
    def gender(self, text):
        if text in ("male", "boy", "man"):
            return "male"
        elif text in ("female", "girl", "woman", "not sure"):
            return "female"

    @classmethod
    # see grammar/akinator_yesno.gram
    def yesno(self, text):
        if text in ("yes", "yep", "correct") or "think" in text:
            return "yes"
        elif text in ("no", "nope", "no way", "not sure"):
            return "no"
        elif text in ("maybe", "perhaps", "dunno") or "don't" in text:
            return "maybe"


class QuestionsMixin(object):
    def QM_init(self, default_voice="Steven", min_confidence=50):
        self.QM_grammar = None
        self.QM_queue = defaultdict(lambda: defer.DeferredQueue())
        self.QM_voice = default_voice
        self.QM_min_confidence = min_confidence

    @defer.inlineCallbacks
    def say(self, text):
        yield self.execute("speak",
                           "tts_commandline|%s|%s" % (self.QM_voice, text))
        ev = yield self.QM_queue["_speak"].get()
        defer.returnValue(ev)

    @defer.inlineCallbacks
    def say_and_wait(self, text, wait="200 15 10 5000"):
        yield self.say(text)
        yield self.wait_for_silence(wait)
        ev = yield self.QM_queue["_wfs"].get()
        defer.returnValue(ev)

    @defer.inlineCallbacks
    def ask(self, text, grammar):
        yield self.say(text)

        if self.QM_grammar is None:
            self.QM_grammar = grammar
            yield self.execute("detect_speech", "pocketsphinx "
                               "%(g)s %(g)s" % dict(g=grammar))
        else:
            if self.QM_grammar != grammar:
                yield self.execute("detect_speech",
                                   "nogrammar %s" % self.QM_grammar)
                yield self.execute("detect_speech", "grammar "
                                   "%(g)s %(g)s" % dict(g=grammar))
                self.QM_grammar = grammar

            yield self.execute("detect_speech", "resume")

        ev = yield self.QM_queue[grammar].get()
        yield self.execute("detect_speech", "pause")
        defer.returnValue(ev)

    def onChannelExecuteComplete(self, ev):
        if ev.variable_current_application == "wait_for_silence":
            self.QM_queue["_wfs"].put(ev)
        elif ev.variable_current_application == "speak":
            self.QM_queue["_speak"].put(ev)

    def onDetectedSpeech(self, ev):
        if ev.Speech_Type == "detected-speech":
            dom = minidom.parseString(ev.rawresponse)
            result = dom.getElementsByTagName("result")[0]
            grammar = result.getAttribute("grammar")
            i = result.getElementsByTagName("interpretation")[0]
            confidence = i.getAttribute("confidence")
            text = i.getElementsByTagName("input")[0].childNodes[0].wholeText

            if int(confidence) >= self.QM_min_confidence:
                self.QM_queue[grammar].put(text)
            else:
                self.QM_queue[grammar].put("")


class AkinatorCall(eventsocket.EventProtocol, QuestionsMixin):
    def connectionMade(self):
        self.QM_init("Susan")
        self.factory.calls += 1
        self.run().addCallback(lambda *v: self.transport.loseConnection())

    def connectionLost(self, why):
        self.factory.calls -= 1

    @defer.inlineCallbacks
    def run(self):
        yield self.connect()   # connect the call
        yield self.myevents()  # tell freeswitch to send all the good stuff
        yield self.answer()

        if self.factory.calls > self.factory.maxcalls:
            yield self.say("...sorry, but I'm talking to a lot of "
                           "people already. Please call me later.")
            defer.returnValue(None)

        yield self.say("\item=Throat "
                       "Hello!! My name is Akinator. "
                       "Think about a real or fictional character, "
                       "and I'll try to guess who it is...")

        answer = yield self.ask("By the way, are you male or female??",
                                "akinator_gender")

        for x in xrange(3):
            answer = Grammar.gender(answer)
            if answer == "male":
                gender, name = "M", "John"
                break
            elif answer == "female":
                gender, name = "F", "Mary"
                break
            elif x < 2:
                answer = yield self.ask("I didn't get that. "
                                        "Boy or girl??", "akinator_gender")
            else:
                yield self.hangup()
                defer.returnValue(None)

        yield self.say_and_wait("And what is your name?")
        yield self.say("Ok! Please tell me more about "
                       "this character...")

        age = random.randrange(22, 38)  # no grammar for this :p
        session = akinator.AkinatorChat(name, age, gender)

        for n, command in enumerate(session):
            text = yield command
            if isinstance(text, akinator.AkinatorQuestion):
                for x in xrange(3):
                    answer = yield self.ask(text.encode("utf-8"),
                                            "akinator_yesno")

                    answer = Grammar.yesno(answer)
                    if answer == "yes":
                        session.put_answer("y")
                        break
                    elif answer == "no":
                        session.put_answer("n")
                        break
                    elif answer == "maybe":
                        session.put_answer("?")
                        break
                    elif x < 2:
                        yield self.say("I didn't get that.")
                    else:
                        yield self.hangup()
                        defer.returnValue(None)

                if not ((n + x) % random.randint(3, 6)):
                    yield self.say([
                        "Ok",
                        "Ok, wait...",
                        "Ok!!",
                        "\item=Swallow",
                        "\item=Mmm",
                        "\item=Oh",
                    ][random.randint(0, 5)])

            elif isinstance(text, akinator.AkinatorAnswer):
                yield self.say("%s \item=Laugh" % text.encode("utf-8"))
                break
            elif isinstance(text, akinator.AkinatorError):
                yield self.say(text.encode("utf-8"))
                break
            else:
                break

        yield self.hangup()

    def unboundEvent(self, evdata, evname):
        #log.err("[eventsocket] unbound Event: %s" % evname)
        pass


class AkinatorFactory(protocol.ServerFactory):
    protocol = AkinatorCall

    def __init__(self, maxcalls=10):
        self.maxcalls = maxcalls
        self.calls = 0


if __name__ == "__main__":
    print __doc__
    log.startLogging(sys.stdout)
    reactor.listenTCP(8888, AkinatorFactory(), interface="0.0.0.0")
    reactor.run()
