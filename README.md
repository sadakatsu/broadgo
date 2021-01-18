# BroadGo

BroadGo is a a [KataGo](https://github.com/lightvector/KataGo) wrapper that aims to give users a broader understanding
of the reviewed positions.  UCTS driven by good training is powerful precisely because it is able to prune
[Go's](https://en.wikipedia.org/wiki/Go_(game)) preposterously broad search tree effectively.  Unfortunately, this has a
direct impact on how useful UCTS-based AIs are for helping human players understand why certain moves receive emphasis
as opposed to others.  This is especially true for weaker players.  To an extent, the result is that human players mimic
AI moves and sequences without understanding them.  Some players seem to assume that the new sequences have made old
choices inferior.  They do not understand that the values the UCTS-oriented networks have learned for moves are best
interpreted in most situations as the network's preference or even its comfort zone.  There are frequently moves that
lead to similar final game results that do not get much search time; humans often conclude that these moves are "bad"
because they do not get good search time.  Thus, BroadGo combine's KataGo's strong UCTS search and positional value
estimation with a forced broad search.  Every possible move in a position gets searched to enough of a depth to enable
users to get a feel for which moves could be viable even though KataGo is disinclined to search it.  In a different but
related vein, it can make starkly clear which moves are not considered because they are in fact bad.
