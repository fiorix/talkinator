talkinator
==========

**NOTE: akinator.com has recently switched to websockets, and I have no plans
to support it. This code is outdated and might be deleted anytime.**

*For the latest source code, see <http://github.com/fiorix/talkinator>*


``talkinator`` is the combination of an interactive web crawler for
<http://akinator.com>, and an
[event socket](http://wiki.freeswitch.org/wiki/Event_Socket) server
application for [FreeSWITCH](http://freeswitch.org).

It is written in Python and Twisted.

It depends on an external text-to-speech system via freeswitch's
[mod_tts_commandline](http://wiki.freeswitch.org/wiki/Mod_tts_commandline) to
synthesize audio, and
[mod_pocketsphinx](http://wiki.freeswitch.org/wiki/Mod_pocketsphinx) for
speech recognition.

I have *no plans* to support it further. Please don't ask.


Live demo
---------

Call **+1 (226) 336-2189** and check [this blog post][info] for more
information. The current voice is female, and is a bit slow to generate audio
because it uses an old server. Sorry.

[info]: http://musta.sh/2012-07-20/twisting-python-and-freeswitch.html
