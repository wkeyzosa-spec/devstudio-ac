fx_version 'bodacious'
games { 'gta5' }

author 'Dev Studio'
description "Dev Studio AC - Advanced Anticheat"

shared_script 'config.lua'
shared_script 'sha256.lua'
shared_script 'antispof.lua'

client_scripts {
    'Enumerators.lua',
    'client.lua', 
    'acloader.lua'
}

server_scripts {
    'server.lua',
    'config_panel.lua',
}

ui_page 'nui/index.html'

files {
    'nui/index.html',
    'nui/css/style.css',
    'nui/js/script.js',
}