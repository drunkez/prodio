idea is to create a web-radio called ProDio, which will include encoder, automation, streaming into all-in-one ( dockerized ) solution, similar soft is already available but i miss some features.
    similar soft now available is BUTT as encoder, libretime.org as broadaster/automation, icecast/shoutcast as streamer, so you can get inspiration of code.

Features:
1, Admin web-interface

Password protected, web interface where admin after log-in can
1a: start/stop stream
1b: upload mp3/ogg files on disk
1c: create/edit/remove playlists
1d: by edit playlis i mean edit name, add/remove song(file) to/from it
1e: create radiolist ( schedule playlists to play)
1f: edit radiolist ( suffle/remove/add )
1g: there should be "download audio" button, that will using yt-dl(or differnet method) download audio from youtube song, provided by URL

any other further cool ideas you might think of

there is a github repo prepared for it

git@github.com:drunkez/prodio.git

store code there
test locally running docker containers after each change
