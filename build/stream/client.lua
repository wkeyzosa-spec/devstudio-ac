-- stream/client.lua
-- Multistream: screenshot capture at 1fps (WebP)
-- Requires: screenshot-basic resource

local isStreaming = false
local frameInterval = 1000
local streamTimer = nil

RegisterNetEvent('dsac:startStream')
AddEventHandler('dsac:startStream', function()
    if isStreaming then return end
    isStreaming = true
    local function capture()
        if not isStreaming then return end
        exports['screenshot-basic']:requestScreenshot(function(err, data)
            if not err and isStreaming then
                TriggerServerEvent('dsac:streamFrame', data)
            end
        end, {encoding = 'webp', quality = 0.6})
    end
    streamTimer = SetInterval(capture, frameInterval)
    capture()
end)

RegisterNetEvent('dsac:stopStream')
AddEventHandler('dsac:stopStream', function()
    isStreaming = false
    if streamTimer then
        ClearInterval(streamTimer)
        streamTimer = nil
    end
end)
