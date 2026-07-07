-- stream/server.lua
-- Multistream: forwards screenshot frames from clients to Flask backend

local backendUrl = Config.BackendUrl or 'http://127.0.0.1:5000'
local serverId = Config.ServerID or 'devstudio'
local maxStreams = 4
local activePlayers = {}

RegisterServerEvent('dsac:streamFrame')
AddEventHandler('dsac:streamFrame', function(base64data)
    local src = source
    local playerId = tostring(src)

    -- Enforce max concurrent streams
    activePlayers[src] = true
    local count = 0
    for k, _ in pairs(activePlayers) do
        count = count + 1
    end
    if count > maxStreams and not activePlayers[src] then
        TriggerClientEvent('dsac:stopStream', src)
        return
    end

    PerformHttpRequest(
        backendUrl .. '/api/server/' .. serverId .. '/stream/' .. playerId,
        function(err, text, headers)
            if err == 404 or err == 0 then
                TriggerClientEvent('dsac:stopStream', src)
                activePlayers[src] = nil
            end
        end,
        'POST',
        json.encode({frame = base64data}),
        {['Content-Type'] = 'application/json'}
    )
end)

-- Stop stream when player disconnects
AddEventHandler('playerDropped', function(reason)
    local src = source
    activePlayers[src] = nil
    PerformHttpRequest(
        backendUrl .. '/api/server/' .. serverId .. '/stream/' .. tostring(src),
        function(err, text, headers) end,
        'DELETE',
        '',
        {['Content-Type'] = 'application/json'}
    )
end)
