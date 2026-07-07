local aimbotCounter = {}
local vehicleSpawnCounter = {}
local weaponSpawnCounter = {}
local healthArmorCounter = {}
local tpCounter = {}
local playerPositions = {}

local LICENSE_VALID = false
local LICENSE_INFO = {}

local function verifyLicense()
    local key = Config.LicenseKey
    if not key or key == "" or key:find("XXXXX") then
        print("^1[DevStudioAC] LICENSE NOT CONFIGURED - Set Config.LicenseKey")
        return false
    end
    local data = LoadResourceFile(GetCurrentResourceName(), "licenses.json")
    if not data then
        print("^1[DevStudioAC] licenses.json not found")
        return false
    end
    local ok, licenses = pcall(json.decode, data)
    if not ok or not licenses then
        print("^1[DevStudioAC] Invalid licenses.json")
        return false
    end
    local lic = licenses[key]
    if not lic then
        print("^1[DevStudioAC] License key not found in database")
        return false
    end
    local sig = lic.signature
    if not sig then
        print("^1[DevStudioAC] License has no signature (tampered)")
        return false
    end
    local msg = string.format("created=%s;expires=%s;key=%s;note=%s;server_ip=%s;status=%s;type=%s",
        tostring(lic.created or ""),
        tostring(lic.expires or ""),
        tostring(lic.key or ""),
        tostring(lic.note or ""),
        tostring(lic.server_ip or ""),
        tostring(lic.status or ""),
        tostring(lic.type or ""))
    local hmacSecret = (Config.BanAPI.Enabled and Config.BanAPI.Secret) or "DsAc2024S3cur3K3y!@#"
    local expected = sha256.hmac(hmacSecret, msg)
    if sig ~= expected then
        print("^1[DevStudioAC] License signature mismatch (tampered)")
        return false
    end
    if lic.status ~= "active" then
        print("^1[DevStudioAC] License status: " .. lic.status)
        return false
    end
    if lic.expires then
        local y, M, d, h, m, s = lic.expires:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
        if y then
            local expTime = os.time({year=y, month=M, day=d, hour=h, min=m, sec=s})
            if os.time() > expTime then
                print("^1[DevStudioAC] License EXPIRED on " .. lic.expires)
                return false
            end
        end
    end
    LICENSE_VALID = true
    LICENSE_INFO = lic
    local expiryStr = lic.expires or "Never (Lifetime)"
    print("^2[DevStudioAC] License VALID - Type: " .. lic.type .. ", Expires: " .. expiryStr)
    return true
end

Citizen.CreateThread(function()
    Citizen.Wait(500)
    if not verifyLicense() then
        print("^1[DevStudioAC] LICENSE INVALID - Disabling all anticheat components")
        for k, v in pairs(Config.Components) do
            Config.Components[k] = false
        end
    end
    Citizen.CreateThread(function()
        while true do
            Citizen.Wait(1800000)
            if not verifyLicense() then
                print("^1[DevStudioAC] LICENSE CHECK FAILED - Disabling components")
                for k, v in pairs(Config.Components) do
                    Config.Components[k] = false
                end
            end
        end
    end)
end)

local function checkLicense()
    if not LICENSE_VALID then
        return false
    end
    if LICENSE_INFO.expires then
        local y, M, d, h, m, s = LICENSE_INFO.expires:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+):(%d+)")
        if y then
            local expTime = os.time({year=y, month=M, day=d, hour=h, min=m, sec=s})
            if os.time() > expTime then
                LICENSE_VALID = false
                return false
            end
        end
    end
    return true
end

if Config.Components.AntiTP then
    Citizen.CreateThread(function()
        while true do
            Citizen.Wait(3000)
            local players = GetPlayers()
            for i = 1, #players do
                local src = players[i]
                if not IsPlayerAceAllowed(src, "Anticheat.Bypass") then
                    local ped = GetPlayerPed(src)
                    if ped then
                        local coords = GetEntityCoords(ped)
                        if coords then
                            local x, y, z = table.unpack(coords)
                            local last = playerPositions[src]
                            if last then
                                local dist = #(vector3(last.x, last.y, last.z) - vector3(x, y, z))
                                if dist > Config.TpMaxDistance then
                                    if not tpCounter[src] then tpCounter[src] = 0 end
                                    tpCounter[src] = tpCounter[src] + 1
                                    if tpCounter[src] >= Config.TpTriggerCount then
                                        BanWithLog(src, Config.Messages.TPTriggered, "tp")
                                        tpCounter[src] = 0
                                    end
                                end
                            end
                            playerPositions[src] = { x = x, y = y, z = z }
                        end
                    end
                end
            end
        end
    end)
end

RegisterNetEvent("Anticheat:AimbotDetected")
AddEventHandler("Anticheat:AimbotDetected", function(distance)
    local src = source
    if Config.Components.AntiAimbot and not IsPlayerAceAllowed(src, "Anticheat.Bypass") then
        local ids = ExtractIdentifiers(src)
        local steam = ids.steam
        if not aimbotCounter[steam] then
            aimbotCounter[steam] = 1
        else
            aimbotCounter[steam] = aimbotCounter[steam] + 1
        end
        if aimbotCounter[steam] >= Config.AimbotTriggerCount then
            BanWithLog(src, Config.Messages.AimbotTriggered, "aimbot")
            aimbotCounter[steam] = 0
        end
    end
end)

RegisterNetEvent("Anticheat:VehicleSpawned")
AddEventHandler("Anticheat:VehicleSpawned", function()
    local src = source
    if Config.Components.AntiVehicleSpawn and not IsPlayerAceAllowed(src, "Anticheat.Bypass") then
        local ids = ExtractIdentifiers(src)
        local steam = ids.steam
        if not vehicleSpawnCounter[steam] then
            vehicleSpawnCounter[steam] = 1
        else
            vehicleSpawnCounter[steam] = vehicleSpawnCounter[steam] + 1
        end
        if vehicleSpawnCounter[steam] >= Config.VehicleSpawnLimit then
            BanWithLog(src, Config.Messages.VehicleSpawnTriggered, "spawn")

        end
    end
end)

RegisterNetEvent("Anticheat:WeaponSpawned")
AddEventHandler("Anticheat:WeaponSpawned", function()
    local src = source
    if Config.Components.AntiWeaponSpawn and not IsPlayerAceAllowed(src, "Anticheat.Bypass") then
        local ids = ExtractIdentifiers(src)
        local steam = ids.steam
        if not weaponSpawnCounter[steam] then
            weaponSpawnCounter[steam] = 1
        else
            weaponSpawnCounter[steam] = weaponSpawnCounter[steam] + 1
        end
        if weaponSpawnCounter[steam] >= Config.WeaponSpawnLimit then
            BanWithLog(src, Config.Messages.WeaponSpawnTriggered, "spawn")
            weaponSpawnCounter[steam] = 0
        end
    end
end)

RegisterNetEvent("Anticheat:HealthArmorDetected")
AddEventHandler("Anticheat:HealthArmorDetected", function(type)
    local src = source
    if Config.Components.AntiHealthArmor and not IsPlayerAceAllowed(src, "Anticheat.Bypass") then
        local ids = ExtractIdentifiers(src)
        local steam = ids.steam
        if not healthArmorCounter[steam] then
            healthArmorCounter[steam] = 1
        else
            healthArmorCounter[steam] = healthArmorCounter[steam] + 1
        end
        if healthArmorCounter[steam] >= 3 then
            BanWithLog(src, Config.Messages.HealthArmorTriggered, "health")
            healthArmorCounter[steam] = 0
        end
    end
end)


-- CODE [DO NOT TOUCH]:
BlacklistedEvents = Config.BlacklistedEvents;

local counter = {}

function BanPlayer(src, reason)
    local config = LoadResourceFile(GetCurrentResourceName(), "ac-bans.json")
    local cfg = json.decode(config)
    local ids = ExtractIdentifiers(src);
    local banData = {};
    banData['ID'] = tonumber(getNewBanID());
    banData['reason'] = reason;
    banData['ip'] = ids.ip ~= "" and ids.ip or "NONE SUPPLIED";
    banData['license'] = ids.license ~= "" and ids.license or "NONE SUPPLIED";
    banData['steam'] = ids.steam ~= "" and ids.steam or "NONE SUPPLIED";
    banData['xbl'] = ids.xbl ~= "" and ids.xbl or "NONE SUPPLIED";
    banData['live'] = ids.live ~= "" and ids.live or "NONE SUPPLIED";
    banData['discord'] = ids.discord ~= "" and ids.discord or "NONE SUPPLIED";
    cfg[tostring(GetPlayerName(src))] = banData;
    SaveResourceFile(GetCurrentResourceName(), "ac-bans.json", json.encode(cfg, { indent = true }), -1)
    DSAntiSpoof_BanIdentity(src, reason)
    if Config.BanAPI.Enabled and Config.BanAPI.SyncOnBan then
        local ids = ExtractIdentifiers(src)
        CallBanAPI('/api/ban', 'POST', {
            server_id = GetPanelServerID(),
            ban_id = banData.ID,
            player_name = GetPlayerName(src),
            name = GetPlayerName(src),
            reason = reason,
            category = 'ban',
            ip = ids.ip,
            license = ids.license,
            steam = ids.steam,
            discord = ids.discord,
        })
    end
end

function BanWithLog(src, reason, category)
    local name = GetPlayerName(src)
    BanPlayer(src, reason)
    SendBanEmbed(src, reason, category)
    DropPlayer(src, "[DevStudioAC]: " .. reason)
    LogWebPanel(name, 'ban', reason, 1)
end
function getNewBanID()
    local config = LoadResourceFile(GetCurrentResourceName(), "ac-bans.json")
    local cfg = json.decode(config)
    local banID = 0;
    for k, v in pairs(cfg) do 
        banID = banID + 1;
    end
    return (banID + 1);
end

RegisterNetEvent('Anticheat:CheckStaff')
AddEventHandler('Anticheat:CheckStaff', function()
    local src = source;
    if IsPlayerAceAllowed(src, 'Anticheat.Bypass') then 
        TriggerClientEvent('Anticheat:CheckStaffReturn', src, true);
    else 
        TriggerClientEvent('Anticheat:CheckStaffReturn', src, false);
    end
end)

RegisterNetEvent('Anticheat:ScreenshotSubmit')
AddEventHandler('Anticheat:ScreenshotSubmit', function()
    local src = source;
    if not IsPlayerAceAllowed(src, "Anticheat.Bypass") then 
        local screenshotOptions = {
            encoding = 'png',
            quality = 1
        }    
        local ids = ExtractIdentifiers(src);
        local playerIP = ids.ip;
        local playerSteam = ids.steam;
        local playerLicense = ids.license;
        local playerXbl = ids.xbl;
        local playerLive = ids.live;
        local playerDisc = ids.discord;
        local swUrl = Config.Webhook.Ban.key or Config.Webhook.Ban.silent or ""
        exports['discord-screenshot']:requestCustomClientScreenshotUploadToDiscord(src, swUrl, screenshotOptions, {
            username = '[CUSTOM-AC]',
            avatar_url = '',
            content = '',
            embeds = {
                {
                    color = 16711680,
                    author = {
                        name = '[CUSTOM-AC]',
                        icon_url = ''
                    },
                    title = '[Possible Modder] Player has triggered blacklisted keys...',
                    description = '**__Player Identifiers:__** \n\n'
                    .. '**Server ID:** `' .. src .. '`\n\n'
                    .. '**Username:** `' .. GetPlayerName(src) .. '`\n\n'
                    .. '**IP:** `' .. playerIP .. '`\n\n'
                    .. '**Steam:** `' .. playerSteam .. '`\n\n'
                    .. '**License:** `' .. playerLicense .. '`\n\n'
                    .. '**Xbl:** `' .. playerXbl .. '`\n\n'
                    .. '**Live:** `' .. playerLive .. '`\n\n'
                    .. '**Discord:** `' .. playerDisc .. '`\n\n',
                    footer = {
                        text = "[" .. src .. "]" .. GetPlayerName(src),
                    }
                }
            }
        });
    end
end)


RegisterCommand('ac-unban', function(source, args, rawCommand)
    local src = source;
    if (src <= 0) then
        -- Console unban
        if #args == 0 then 
            -- Not enough arguments
            print('^3[^6DevStudioAC^3] ^1Not enough arguments...');
            return; 
        end
        local banID = args[1];
        if tonumber(banID) ~= nil then
            local playerName = UnbanPlayer(banID);
            if playerName then
                print('^3[^6DevStudioAC^3] ^0Player ^1' .. playerName 
                .. ' ^0has been unbanned from the server by ^2CONSOLE');
            else 
                -- Not a valid ban ID
                print('^3[^6DevStudioAC^3] ^1That is not a valid ban ID. No one has been unbanned!'); 
            end
        end
        return;
    end 
    if IsPlayerAceAllowed(src, "DevStudioAC.ACban") then 
        if #args == 0 then 
            -- Not enough arguments
            TriggerClientEvent('chatMessage', src, '^3[^6DevStudioAC^3] ^1Not enough arguments...');
            return; 
        end
        local banID = args[1];
        if tonumber(banID) ~= nil then 
            -- Is a valid ban ID 
            local playerName = UnbanPlayer(banID);
            if playerName then
                TriggerClientEvent('chatMessage', -1, '^3[^6DevStudioAC^3] ^0Player ^1' .. playerName 
                .. ' ^0has been unbanned from the server by ^2' .. GetPlayerName(src)); 
            else 
                -- Not a valid ban ID
                TriggerClientEvent('chatMessage', src, '^3[^6DevStudioAC^3] ^1That is not a valid ban ID. No one has been unbanned!'); 
            end
        else 
            -- Not a valid number
            TriggerClientEvent('chatMessage', src, '^3[^6DevStudioAC^3] ^1That is not a valid number...'); 
        end
    end
end)
function UnbanPlayer(banID)
    local config = LoadResourceFile(GetCurrentResourceName(), "ac-bans.json")
    local cfg = json.decode(config)
    for k, v in pairs(cfg) do 
        local id = tonumber(v['ID']);
        if id == tonumber(banID) then 
            local name = k;
            cfg[k] = nil;
            SaveResourceFile(GetCurrentResourceName(), "ac-bans.json", json.encode(cfg, { indent = true }), -1)
    if Config.BanAPI.Enabled then
        CallBanAPI('/api/ban', 'POST', {
            unban = true,
            ban_id = tonumber(banID),
            server_id = GetPanelServerID(),
        })
    end
            return name;
        end
    end
    return false;
end 
--[[
@param src - The player server ID supplied

function isBanned(src)
    FOUND: returns { banID: tonumber(banID), reason: tostring(reason) }
    NOT FOUND: returns false
]]--
function isBanned(src)
    local config = LoadResourceFile(GetCurrentResourceName(), "ac-bans.json")
    local cfg = json.decode(config)
    local ids = ExtractIdentifiers(src);
    local playerIP = ids.ip;
    local playerSteam = ids.steam;
    local playerLicense = ids.license;
    local playerXbl = ids.xbl;
    local playerLive = ids.live;
    local playerDisc = ids.discord;
    for k, v in pairs(cfg) do 
        local reason = v['reason']
        local id = v['ID']
        local ip = v['ip']
        local license = v['license']
        local steam = v['steam']
        local xbl = v['xbl']
        local live = v['live']
        local discord = v['discord']
        if tostring(ip) == tostring(playerIP) then return { ['banID'] = id, ['reason'] = reason } end;
        if tostring(license) == tostring(playerLicense) then return { ['banID'] = id, ['reason'] = reason } end;
        if tostring(steam) == tostring(playerSteam) then return { ['banID'] = id, ['reason'] = reason } end;
        if tostring(xbl) == tostring(playerXbl) then return { ['banID'] = id, ['reason'] = reason } end;
        if tostring(live) == tostring(playerLive) then return { ['banID'] = id, ['reason'] = reason } end;
        if tostring(discord) == tostring(playerDisc) then return { ['banID'] = id, ['reason'] = reason } end;
    end
    return false;
end
function GetBans()
    local config = LoadResourceFile(GetCurrentResourceName(), "ac-bans.json")
    local cfg = json.decode(config)
    return cfg;
end

local function CallBanAPI(endpoint, method, data)
    if not Config.BanAPI.Enabled then return nil end
    local url = Config.BanAPI.Url .. endpoint
    local secret = Config.BanAPI.Secret
    local body = data and json.encode(data) or nil
    local respData = nil
    local reqDone = false
    PerformHttpRequest(url, function(err, text, headers)
        if err == 200 then
            respData = text
        end
        reqDone = true
    end, method or 'GET', body, {
        ['Content-Type'] = 'application/json',
        ['Authorization'] = 'Bearer ' .. sha256.hmac(secret, endpoint .. (body or ""))
    })
    local timeout = 0
    while not reqDone and timeout < 100 do
        Citizen.Wait(100)
        timeout = timeout + 1
    end
    if respData then
        local ok, decoded = pcall(json.decode, respData)
        if ok and decoded then
            return decoded
        end
    end
    return nil
end

local function SyncBansFromAPI()
    if not Config.BanAPI.Enabled or not Config.BanAPI.SyncOnJoin then return end
    local sid = GetPanelServerID()
    local bans = CallBanAPI('/api/server/' .. sid .. '/bans', 'GET')
    if not bans or type(bans) ~= 'table' then return end
    local current = LoadResourceFile(GetCurrentResourceName(), "ac-bans.json")
    local cfg = current and json.decode(current) or {}
    for name, banData in pairs(bans) do
        cfg[name] = banData
    end
    SaveResourceFile(GetCurrentResourceName(), "ac-bans.json", json.encode(cfg, { indent = true }), -1)
    local count = 0; for _,_ in pairs(bans) do count = count + 1 end
    print("[DevStudioAC] Sincronizzati " .. count .. " ban dal server centrale")
end

local function PushWebPanel(method, endpoint, data, cb)
    if not Config.BanAPI.Enabled then return end
    local url = Config.BanAPI.Url .. endpoint
    local body = data and json.encode(data) or nil
    PerformHttpRequest(url, function(err, text, headers)
        if cb then cb(err, text) end
    end, method or 'POST', body, {
        ['Content-Type'] = 'application/json',
    })
end

local function GetPanelServerID()
    if Config.ServerID and Config.ServerID ~= "auto" then
        return Config.ServerID
    end
    return sha256.hmac("DsAcServerId", Config.LicenseKey):sub(1, 16)
end

function SyncWebPanelPlayers()
    if not Config.BanAPI.Enabled then return end
    local sid = GetPanelServerID()
    local players = {}
    local staffCount = 0
    for _, pid in pairs(GetPlayers()) do
        local ids = ExtractIdentifiers(pid)
        local name = GetPlayerName(pid)
        local playtime = 0
        if playTracker[ids.ip] then playtime = playTracker[ids.ip] end
        if IsPlayerAceAllowed(pid, 'Anticheat.Bypass') or IsPlayerAceAllowed(pid, 'DevStudioAC.admin') then
            staffCount = staffCount + 1
        end
        local pos = playerPositions[pid]
        local coords = pos or { x = 0, y = 0, z = 0 }
        local country = GetPlayerCountry(pid)
        table.insert(players, {
            id = tonumber(pid),
            name = name,
            steam = ids.steam,
            ip = ids.ip,
            license = ids.license,
            discord = ids.discord,
            xbl = ids.xbl,
            live = ids.live,
            fivem = ids.fivem,
            playtime = playtime,
            pos_x = coords.x,
            pos_y = coords.y,
            pos_z = coords.z,
            country = country,
        })
    end
    PushWebPanel('POST', '/api/server/' .. sid .. '/players', players)
    PushWebPanel('POST', '/api/server/' .. sid .. '/heartbeat', {
        server_name = GetConvar("sv_hostname", "DEVSTUDIO"),
        player_count = #players,
        staff_count = staffCount,
        uptime = math.floor(GetGameTimer() / 3600000) .. "h",
    })
end

function LogWebPanel(playerName, action, reason, detections)
    if not Config.BanAPI.Enabled then return end
    local sid = GetPanelServerID()
    PushWebPanel('POST', '/api/server/' .. sid .. '/log', {
        player_name = playerName,
        action = action,
        reason = reason,
        detections = detections or 1,
    })
end

-- Sync admins to web panel
local function SyncAdminsToPanel()
    if not Config.BanAPI.Enabled then return end
    local sid = GetPanelServerID()
    local admins = {}
    for _, pid in pairs(GetPlayers()) do
        if IsPlayerAceAllowed(pid, 'DevStudioAC.admin') or IsPlayerAceAllowed(pid, 'Anticheat.Bypass') then
            local ids = ExtractIdentifiers(pid)
            table.insert(admins, {
                player_id = tonumber(pid),
                name = GetPlayerName(pid),
                ace = IsPlayerAceAllowed(pid, 'DevStudioAC.admin') and 'admin' or 'bypass',
                online = true,
                steam = ids.steam or '',
            })
        end
    end
    PushWebPanel('POST', '/api/server/' .. sid .. '/admins', admins)
end

-- Fetch config from web panel and apply
local function FetchConfigFromPanel()
    if not Config.BanAPI.Enabled then return end
    local sid = GetPanelServerID()
    local url = Config.BanAPI.Url .. '/api/server/' .. sid .. '/config'
    PerformHttpRequest(url, function(err, text)
        if err ~= 200 or not text then return end
        local ok, data = pcall(json.decode, text)
        if not ok or not data or not data.config then return end
        local webConfig = data.config
        local components = webConfig.Components
        local limits = webConfig.Limits
        if components then
            for key, val in pairs(components) do
                Config.Components[key] = val == true
                PanelConfig.Set(key, val == true)
            end
        end
        if limits then
            for key, val in pairs(limits) do
                PanelConfig.Set(key, tonumber(val) or PanelConfig.Defaults[key])
            end
        end
        PanelConfig.Save()
    end, 'GET', '', {
        ['Authorization'] = 'Bearer ' .. sha256.hmac(Config.BanAPI.Secret, '/api/server/' .. sid .. '/config'),
        ['Content-Type'] = 'application/json',
    })
end

-- Execute pending kicks from web panel
local function ExecutePendingKicks()
    if not Config.BanAPI.Enabled then return end
    local sid = GetPanelServerID()
    local url = Config.BanAPI.Url .. '/api/server/' .. sid .. '/heartbeat'
    PerformHttpRequest(url, function(err, text)
        if err ~= 200 or not text then return end
        local ok, data = pcall(json.decode, text)
        if not ok or not data then return end
        if data.pending_kicks and #data.pending_kicks > 0 then
            local executed = {}
            for _, kick in ipairs(data.pending_kicks) do
                local target = kick.player_id
                if GetPlayerName(target) then
                    DropPlayer(target, "[DevStudioAC] Kicked via web dashboard")
                    table.insert(executed, kick.id)
                end
            end
            if #executed > 0 then
                local sid = GetPanelServerID()
                PushWebPanel('POST', '/api/server/' .. sid .. '/heartbeat', {
                    kicks_executed = executed,
                })
            end
        end
    end, 'POST', '{}', {
        ['Content-Type'] = 'application/json',
    })
end

local function GetPanelPendingCommands()
    if not Config.BanAPI.Enabled then return end
    local sid = GetPanelServerID()
    local url = Config.BanAPI.Url .. '/api/server/' .. sid .. '/commands/pending'
    PerformHttpRequest(url, function(err, text)
        if err ~= 200 or not text then return end
        local ok, data = pcall(json.decode, text)
        if not ok or not data or not data.commands then return end
        for _, cmd in ipairs(data.commands) do
            local cmdId = cmd.id
            local action = cmd.action
            local targetId = tonumber(cmd.target_id)
            local targetName = cmd.target_name or "Unknown"
            local adminName = cmd.admin_name or ""
            local executed = false
            if action == "spectate" then
                for _, pid in pairs(GetPlayers()) do
                    if adminName ~= "" and GetPlayerName(pid) == adminName then
                        if targetId and GetPlayerName(targetId) then
                            TriggerClientEvent('acpanel:startSpectate', pid, targetId)
                            print("[DevStudioAC] Web: " .. adminName .. " spectating " .. targetName)
                            executed = true
                        end
                        break
                    end
                end
            elseif action == "teleport" then
                for _, pid in pairs(GetPlayers()) do
                    if adminName ~= "" and GetPlayerName(pid) == adminName then
                        if targetId then
                            TriggerClientEvent('anticheat:TeleportToPlayer', pid, targetId)
                            print("[DevStudioAC] Web: " .. adminName .. " teleporting to " .. targetName)
                            executed = true
                        end
                        break
                    end
                end
            elseif action == "wipe" then
                if targetId then
                    EntityWipe(0, targetId)
                    print("[DevStudioAC] Web: Entity wipe on " .. targetName)
                    executed = true
                end
            end
            if executed then
                PerformHttpRequest(Config.BanAPI.Url .. '/api/server/' .. sid .. '/commands/execute/' .. cmdId, function() end, 'POST', '{}', {
                    ['Content-Type'] = 'application/json',
                })
            end
        end
    end, 'GET', '', {
        ['Content-Type'] = 'application/json',
    })
end

local playTracker = {}
Citizen.CreateThread(function()
    while true do 
        Wait(0);
        for _, id in pairs(GetPlayers()) do 
            local ip = ExtractIdentifiers(id).ip;
            if playTracker[ip] ~= nil then 
                playTracker[ip] = playTracker[ip] + 1;
            else 
                playTracker[ip] = 1;
            end
        end
        Wait((1000 * 60)); -- Every minute 
    end
end)
function GetLatest(count)
    local latest = {};
    local lowest = 9999999;
    local lowestUser = nil;
    local ourCount = 0;
    local ourArr = {};
    for ip, playtime in pairs(playTracker) do 
        ourArr[ip] = playtime;
    end
    local retArr = {};
    while ourCount < count do 
        lowest = nil;
        local lowestIP = nil;
        lowestUser = nil;
        for ip, playtime in pairs(ourArr) do 
            for _, pid in pairs(GetPlayers()) do 
                local playerIP = ExtractIdentifiers(pid).ip;
                if tostring(ip) == tostring(playerIP) then 
                    if lowest == nil or lowest >= playtime then 
                        lowestIP = ip;
                        lowest = playtime 
                        lowestUser = pid;
                    end
                end 
            end 
        end
        if lowest ~= nil then 
            ourArr[lowestIP] = nil;
            table.insert(retArr, {lowestUser, lowest});
        end 
        ourCount = ourCount + 1;
    end
    return retArr;
end
local function ExtractIP(pid)
    local ids = ExtractIdentifiers(pid)
    return ids.ip and ids.ip:gsub("^ip:", "") or ""
end

local countryCache = {}
local function GetPlayerCountry(pid)
    local ip = ExtractIP(pid)
    if not ip or ip == "" then return "" end
    if countryCache[ip] then return countryCache[ip] end
    PerformHttpRequest("http://ip-api.com/json/" .. ip, function(err, text)
        if err == 200 and text then
            local ok, data = pcall(json.decode, text)
            if ok and data and data.countryCode then
                countryCache[ip] = data.countryCode
            end
        end
    end, 'GET', '', { ['Content-Type'] = 'application/json' })
    return ""
end

RegisterCommand("entitywipe", function(source, args, raw)
    local playerID = args[1]
    if (IsPlayerAceAllowed(source, "AntiCheat.Moderation")) then
        if (playerID ~= nil and tonumber(playerID) ~= nil) then 
            EntityWipe(source, tonumber(playerID))
        end
    end
end, false)
function EntityWipe(source, target)
    TriggerClientEvent("anticheat:EntityWipe", -1, tonumber(target))
end
RegisterCommand("latest", function(source, args, rawCommand) 
    local latestUsers = GetLatest(6);
    for i = 1, #latestUsers do 
        local user = latestUsers[i][1];
        local playTime = latestUsers[i][2];
        TriggerClientEvent('chatMessage', source, "^5[^1DevStudioAC^5] ^3Player ^3[^4".. tostring(user) .. "^3] ^4" .. 
            GetPlayerName(user) .. " ^3has played ^4" .. playTime ..
            " ^3minutes so far...");
    end
end)
--[[
Citizen.CreateThread(function()
    while true do 
        Wait(40000); -- Every 40 seconds 
        for _, id in pairs(GetPlayers()) do 
            if isBanned(id) then 
                -- Banned, kick em 
                DropPlayer(id, "[DevStudioAC] " .. bans[tostring(playerIP)]);
            end
        end
    end
end)
]]--
if Config.BanAPI.Enabled then
    Citizen.CreateThread(function()
        local tick = 0
        while true do
            Citizen.Wait(15000)
            tick = tick + 1
            ExecutePendingKicks()
            GetPanelPendingCommands()
            if tick % 2 == 0 then
                SyncWebPanelPlayers()
                SyncAdminsToPanel()
            end
            if tick % 4 == 0 then
                FetchConfigFromPanel()
            end
            if tick % 20 == 0 then
                SyncBansFromAPI()
                print("[DevStudioAC] Sincronizzazione completa")
            end
        end
    end)
end
RegisterNetEvent("ANTICHEAT:FINGERPRINT")
AddEventHandler("ANTICHEAT:FINGERPRINT", function(fingerprint)
    local src = source
    if not fingerprint or fingerprint == "" then return end
    local ids = ExtractIdentifiers(src)
    DSAntiSpoof_UpdatePlayer(src, ids, fingerprint)
end)

function OnPlayerConnecting(name, setKickReason, deferrals)
    deferrals.defer();
    local src = source;
    print("[DevStudioAC] Checking ban data for "..GetPlayerName(src));
    SyncBansFromAPI();
    Citizen.Wait(100);
    local banned = false;
    local ban = isBanned(src);
    Citizen.Wait(100);
    if ban then 
        local reason = ban['reason'];
        local printMessage = nil;
        if string.find(reason, "[DevStudioAC]") then 
            printMessage = "" 
        else 
            printMessage = "[DevStudioAC] " 
        end 
        print("[BANNED PLAYER] Player " .. GetPlayerName(src) .. " tried to join, but was banned for: " .. reason);
        deferrals.done(printMessage .. "(BAN ID: " .. ban['banID'] .. ") " .. reason);
        banned = true;
        CancelEvent();
        return;
    end
    if not banned and Config.AntiSpoof and Config.AntiSpoof.Enabled then
        local spoofer = DSAntiSpoof_IsSpoofer(src)
        if spoofer then
            local reason = "[DevStudioAC] " .. (spoofer.ban_reason or "Spoofing rilevato")
            print("[SPOOFER] Player " .. GetPlayerName(src) .. " caught by identity graph: " .. reason)
            deferrals.done("(BAN ID: " .. (spoofer.ban_id or "?") .. ") " .. reason)
            banned = true;
            CancelEvent();
            return;
        end
    end
    if not banned then 
        deferrals.done();
    end
end
RegisterCommand("aclicense", function(source, args, raw)
    local src = source
    if src ~= 0 and not IsPlayerAceAllowed(src, "DevStudioAC.admin") then
        TriggerClientEvent('chatMessage', src, "^1[DevStudioAC] You don't have permission")
        return
    end
    if checkLicense() then
        local expiryStr = LICENSE_INFO.expires or "LIFETIME"
        local msg = string.format("^2[DevStudioAC] License: ^5%s ^2| Type: ^5%s ^2| Expires: ^5%s",
            LICENSE_INFO.key, LICENSE_INFO.type, expiryStr)
        if src == 0 then
            print(msg)
        else
            TriggerClientEvent('chatMessage', src, msg)
        end
    else
        local msg = "^1[DevStudioAC] License INVALID or EXPIRED"
        if src == 0 then
            print(msg)
        else
            TriggerClientEvent('chatMessage', src, msg)
        end
    end
end, false)

RegisterCommand("aclicense-reload", function(source, args, raw)
    local src = source
    if src ~= 0 and not IsPlayerAceAllowed(src, "DevStudioAC.admin") then
        if src ~= 0 then
            TriggerClientEvent('chatMessage', src, "^1[DevStudioAC] You don't have permission")
        end
        return
    end
    local valid = verifyLicense()
    if valid then
        print("^2[DevStudioAC] License re-verified successfully")
        if src > 0 then
            TriggerClientEvent('chatMessage', src, "^2[DevStudioAC] License re-verified successfully")
        end
    else
        print("^1[DevStudioAC] License verification failed")
        if src > 0 then
            TriggerClientEvent('chatMessage', src, "^1[DevStudioAC] License verification failed")
        end
    end
end, false)

RegisterCommand("acban", function(source, args, raw)
    -- /acban <id> <reason> 
    local src = source;
    if IsPlayerAceAllowed(src, "DevStudioAC.ACban") then 
        -- They can ban players this way
        if #args < 2 then 
            -- Not valid enough num of arguments 
            TriggerClientEvent('chatMessage', source, "^5[^1DevStudioAC^5] ^1ERROR: You have supplied invalid amount of arguments... " ..
                "^2Proper Usage: /acban <id> <reason>");
            return;
        end
        local id = args[1]
        if ExtractIdentifiers(args[1]) ~= nil then 
            -- Valid player supplied 
            local ids = ExtractIdentifiers(id);
            local steam = ids.steam;
            local gameLicense = ids.license;
            local discord = ids.discord;
            local reason = table.concat(args, ' '):gsub(args[1] .. " ", "");
            local manualReason = "Banned by " .. GetPlayerName(src) .. " for: " .. reason
            BanPlayer(args[1], reason);
            SendBanEmbed(args[1], manualReason, "manual")
            DropPlayer(id, "[DevStudioAC]: " .. manualReason);
        else 
            -- Not a valid player supplied 
            TriggerClientEvent('chatMessage', source, "^5[^1DevStudioAC^5] ^1ERROR: There is no valid player with that ID online... " ..
                "^2Proper Usage: /acban <id> <reason>");
        end
    end
end)
AddEventHandler("playerConnecting", OnPlayerConnecting)

RegisterServerEvent("Anticheat:NoClip")
AddEventHandler("Anticheat:NoClip", function(distance)
    if Config.Components.AntiNoclip and not IsPlayerAceAllowed(source, "Anticheat.Bypass") then
        local id = source;
        local ids = ExtractIdentifiers(id);
        if counter[ids.steam] ~= nil then 
            counter[ids.steam] = counter[ids.steam] + 1;
        else 
            counter[ids.steam] = 1;
        end
        if counter[ids.steam] ~= nil and counter[ids.steam] >= Config.NoClipTriggerCount then 
            BanWithLog(id, Config.Messages.NoClipTriggered, "noclip")
        end 
        Wait(6000);
        counter[ids.steam] = counter[ids.steam] - 1;
    end
end)

-- Props to Lance Good for this code (most of it at least): [https://github.com/DevLanceGood]
function IsLegal(entity) 
    local model = GetEntityModel(entity)
    if (model ~= nil) then
        if (GetEntityType(entity) == 1 and GetEntityPopulationType(entity) == 7) then 
            local WhitelistPedModels = Config.WhitelistPedModels;
            local isWhitelisted = false;
            for i = 1, #WhitelistPedModels do 
                if GetHashKey(WhitelistPedModels[i]) == model then 
                    isWhitelisted = true;
                end 
            end 
            if not isWhitelisted then 
                --return "Spawning Peds";
				return false;
            else
                return false;
            end 
        end
        for i=1, #Config.BlacklistedModels do 
            local hashkey = tonumber(Config.BlacklistedModels[i]) ~= nil and tonumber(Config.BlacklistedModels[i]) or GetHashKey(Config.BlacklistedModels[i]) 
            if (hashkey == model) then
                if (GetEntityPopulationType(entity) ~= 7) then
                    return Config.BlacklistedModels[i];
                else
                    return false 
                end
            end
        end
    end
    return false
end
-- End props 
RegisterNetEvent("Anticheat:ModderESX")
AddEventHandler("Anticheat:ModderESX", function(type, reason)
    local id = source;
    if Config.BanComponents.AntiESX then
        BanWithLog(id, reason, "esx")
    else
        SendLog(Config.Webhook.Ban.esx, "⚠️ " .. type, 16753920, id, reason)
        DropPlayer(id, reason)
    end
end)
RegisterNetEvent("Anticheat:Modder")
AddEventHandler("Anticheat:Modder", function(type, reason)
    local id = source;
    if Config.BanComponents.AntiCommands then
        BanWithLog(id, reason, "command")
    else
        SendLog(Config.Webhook.Ban.command, "⚠️ " .. type, 16753920, id, reason)
        DropPlayer(id, reason)
    end
end)
RegisterNetEvent("Anticheat:ModderNoKick")
AddEventHandler("Anticheat:ModderNoKick", function(type, reason, bool)
    local id = source;
    SendLog(Config.Webhook.Ban.silent, "⚠️ " .. type, 16753920, id, reason)
    if bool then
        DropPlayer(id, reason)
    end
end)
RegisterNetEvent("Anticheat:SpectateTrigger")
AddEventHandler("Anticheat:SpectateTrigger", function(reason)
    if Config.Components.AntiSpectate and not IsPlayerAceAllowed(source, "Anticheat.Bypass") then
        local id = source;
        BanWithLog(id, reason, "spectate")
    end
end)
AddEventHandler('chatMessage', function(source, name, msg)
    local id = source;
    local realName = GetPlayerName(source);
    if (name ~= realName) then
        local extra = "Messaggio falsificato: `" .. msg .. "` come `" .. name .. "`"
        if Config.BanComponents.AntiFakeMessage then
            BanWithLog(id, Config.Messages.ChatMessageTriggered, "chat")
        else
            SendLog(Config.Webhook.Ban.chat, "⚠️ **Fake Chat Message**", 16753920, id, Config.Messages.ChatMessageTriggered, extra)
            DropPlayer(id, "[DevStudioAC]: " .. Config.Messages.ChatMessageTriggered)
        end
    end
end)

function GetEntityOwner(entity)
    if (not DoesEntityExist(entity)) then 
        return nil 
    end
    local owner = NetworkGetEntityOwner(entity)
    if (GetEntityPopulationType(entity) ~= 7) then return nil end
    return owner
end

AddEventHandler('explosionEvent', function(sender, ev)
    local sender = tonumber(sender)
    CancelEvent()
    if (sender ~= nil and sender > 0) then 
        CancelEvent()
    end
end)


for i=1, #BlacklistedEvents, 1 do
    RegisterServerEvent(BlacklistedEvents[i])
    AddEventHandler(BlacklistedEvents[i], function()
        local id = source;
        local reason = Config.Messages.BlacklistedEventTriggered:gsub("{EVENT}", BlacklistedEvents[i]);
        BanWithLog(id, "[DevStudioAC]: " .. reason, "event")
    end)
end

AddEventHandler("entityCreating",  function(entity)
    local owner = GetEntityOwner(entity)
    local cancelled = false
    local model = IsLegal(entity);
    if (model) then 
        if (owner ~= nil and owner > 0) then
            local id = owner;
            if IsPlayerAceAllowed(id, "Anticheat.Bypass") then return end
            local reason = Config.Messages.BlacklistedEntity:gsub("{ENTITY}", tostring(model));
            SendLog(Config.Webhook.Ban.entity, "🚫 **BAN [ENTITY]**", 16724787, id, "Spawned entity: " .. tostring(model))
            DropPlayer(owner, reason);
        end
        CancelEvent()
        cancelled = true
        return
    end
    if owner ~= nil and owner > 0 then
        local id = owner
        if IsPlayerAceAllowed(id, "Anticheat.Bypass") then return end
        local eType = GetEntityType(entity)
        if eType == 2 and Config.Components.AntiVehicleSpawn then
            if GetEntityPopulationType(entity) ~= 7 then
                TriggerClientEvent("Anticheat:VehicleSpawned", id)
            end
        end
        if eType == 3 and Config.Components.AntiWeaponSpawn then
            if GetEntityPopulationType(entity) ~= 7 then
                local model = GetEntityModel(entity)
                for i = 1, #Config.BlacklistedWeapons do
                    if GetHashKey(Config.BlacklistedWeapons[i]) == model then
                        CancelEvent()
                        cancelled = true
                        TriggerClientEvent("Anticheat:WeaponSpawned", id)
                        break
                    end
                end
            end
        end
    end
end)
function ExtractIdentifiers(src)
    local identifiers = {
        steam = "",
        ip = "",
        discord = "",
        license = "",
        license2 = "",
        xbl = "",
        live = "",
        fivem = ""
    }

    for i = 0, GetNumPlayerIdentifiers(src) - 1 do
        local id = GetPlayerIdentifier(src, i)

        if string.find(id, "steam") then
            identifiers.steam = id
        elseif string.find(id, "ip") then
            identifiers.ip = id
        elseif string.find(id, "discord") then
            identifiers.discord = id
        elseif string.find(id, "license2") then
            identifiers.license2 = id
        elseif string.find(id, "license") then
            identifiers.license = id
        elseif string.find(id, "xbl") then
            identifiers.xbl = id
        elseif string.find(id, "live") then
            identifiers.live = id
        elseif string.find(id, "fivem") then
            identifiers.fivem = id
        end
    end

    return identifiers
end

function GetIdentifiers(src)
    local ids = { steam = "", ip = "", discord = "", license = "", license2 = "", xbl = "", live = "", fivem = "" }
    for i = 0, GetNumPlayerIdentifiers(src) - 1 do
        local id = GetPlayerIdentifier(src, i)
        if string.find(id, "steam") then ids.steam = id
        elseif string.find(id, "ip") then ids.ip = id
        elseif string.find(id, "discord") then ids.discord = id
        elseif string.find(id, "license2") then ids.license2 = id
        elseif string.find(id, "license") then ids.license = id
        elseif string.find(id, "xbl") then ids.xbl = id
        elseif string.find(id, "live") then ids.live = id
        elseif string.find(id, "fivem") then ids.fivem = id end
    end
    return ids
end

function BuildIdentifierString(ids)
    local str = "**__Identificativi:__**\n"
    if ids.steam and ids.steam ~= "" then
        local sid = ids.steam:gsub("steam:", "")
        local dec = tonumber(sid, 16)
        str = str .. "🔵 **Steam:** [`" .. ids.steam .. "`](https://steamcommunity.com/profiles/" .. (dec or sid) .. ")\n"
    end
    if ids.ip and ids.ip ~= "" then str = str .. "🌐 **IP:** `" .. ids.ip .. "`\n" end
    if ids.license and ids.license ~= "" then str = str .. "📄 **License:** `" .. ids.license .. "`\n" end
    if ids.license2 and ids.license2 ~= "" then str = str .. "📄 **License2:** `" .. ids.license2 .. "`\n" end
    if ids.discord and ids.discord ~= "" then
        local did = ids.discord:gsub("discord:", "")
        str = str .. "💬 **Discord:** <@" .. did .. "> (`" .. did .. "`)\n"
    end
    if ids.xbl and ids.xbl ~= "" then str = str .. "🎮 **XBL:** `" .. ids.xbl .. "`\n" end
    if ids.live and ids.live ~= "" then str = str .. "🆔 **Live:** `" .. ids.live .. "`\n" end
    if ids.fivem and ids.fivem ~= "" then str = str .. "🔑 **FiveM:** `" .. ids.fivem .. "`\n" end
    return str
end

BAN_COLORS = {
    aimbot = 16711680,
    noclip = 16711680,
    silent = 10181046,
    spawn = 16744192,
    health = 16747520,
    spectate = 16753920,
    command = 16737380,
    event = 16724787,
    entity = 16724787,
    esx = 16724787,
    chat = 16753920,
    resource = 16744192,
    key = 10181046,
    manual = 16711680,
}

function SendLog(webhook, title, color, playerId, reason, extra)
    if not webhook or webhook == "" then return end
    local name = GetPlayerName(playerId)
    local ids = GetIdentifiers(playerId)
    local desc = ""
    if reason then desc = desc .. "**Ragione:** " .. reason .. "\n\n" end
    desc = desc .. BuildIdentifierString(ids)
    if extra then desc = desc .. "\n" .. extra end
    local embed = {{
        ["color"] = color or 16711680,
        ["title"] = title,
        ["description"] = desc,
        ["footer"] = { ["text"] = "Server ID: " .. playerId .. " | " .. (name or "Unknown") },
        ["timestamp"] = os.date("!%Y-%m-%dT%H:%M:%SZ"),
    }}
    PerformHttpRequest(webhook, function(err, text, headers) end, 'POST',
        json.encode({ username = "DevStudio AC", embeds = embed }),
        { ['Content-Type'] = 'application/json' })
end

function SendBanEmbed(playerId, reason, category)
    category = category or "silent"
    local color = BAN_COLORS[category] or 16711680
    local label = category:upper()
    local webhook = Config.Webhook.Ban[category]
    if not webhook or webhook == "" then
        for _, v in pairs(Config.Webhook.Ban) do
            if v and v ~= "" then webhook = v; break end
        end
    end
    SendLog(webhook, "🚫 **BAN [" .. label .. "]**", color, playerId, reason)
    if not webhook or webhook == "" then return end
    local screenshotOptions = { encoding = 'png', quality = 1 }
    exports['discord-screenshot']:requestCustomClientScreenshotUploadToDiscord(playerId, webhook, screenshotOptions, {
        username = 'DevStudio AC',
        content = '',
        embeds = {{
            color = color,
            title = "📸 **Screenshot [" .. label .. "]**",
            description = "Categoria: " .. label .. " | " .. GetPlayerName(playerId),
            footer = { ["text"] = "Server ID: " .. playerId },
        }}
    })
end



--Optional Features depending on the server disable if not suitable for yours!
AddEventHandler("clearPedTasksEvent", function(sender, data)
    if Config.Components.AntiCancelAnimations then 
    CancelEvent()
    end 
    -- Stops other players kicking people out of cars
end)

AddEventHandler('removeWeaponEvent', function(sender, data)
    if Config.Components.AntiRemoveOtherPlayersWeapons then 
        CancelEvent()
    end 
    -- Would only affect if you have scripts removing other people's weapons. (stops players removing other players weapons)
end)

AddEventHandler('giveWeaponEvent', function(sender, data)
    if Config.Components.StopOtherPlayersGivingEachOtherWeapons then 
    CancelEvent()
    end 
    -- Stops other players giving people weapons (doesn't affect single people unless you have give weapons on menus and etc.)
end)



-- Player join/leave logging
AddEventHandler("playerConnecting", function(name, setKickReason, deferrals)
    local src = source
    if Config.Webhook.LogJoins then
        Citizen.CreateThread(function()
            Citizen.Wait(2000)
            SendLog(Config.Webhook.JoinURL, "🟢 **PLAYER JOIN**", 5763719, src, "Nome: " .. name)
        end)
    end
end)

AddEventHandler("playerDropped", function(reason)
    local src = source
    if Config.Webhook.LogLeaves then
        local dropReason = reason or "Disconnected"
        SendLog(Config.Webhook.LeaveURL, "🔴 **PLAYER LEFT**", 15548997, src, "Ragione: " .. dropReason)
    end
end)

CreateThread(function()
    if Config.Components.ModMenuChecks then
        Wait(1000)
        local added = false
        for i = 1, GetNumResources() do
            local resource_id = i - 1
            local resource_name = GetResourceByFindIndex(resource_id)
            if resource_name ~= GetCurrentResourceName() then
                for k, v in pairs({'fxmanifest.lua', '__resource.lua'}) do
                    local data = LoadResourceFile(resource_name, v)
                    if data and type(data) == 'string' and string.find(data, 'acloader.lua') == nil then
                        data = data .. '\nclient_script "@' .. GetCurrentResourceName() .. '/acloader.lua"'
                        SaveResourceFile(resource_name, v, data, -1)
                        print('Added to resource: ' .. resource_name)
                        added = true
                    end
                end
            end
        end
        if added then
            print('Modified 1 or more resources. It is required to restart your server so these changes can now take place.')
        end
    else 
        Wait(1000)
        local added = false
        for i = 1, GetNumResources() do
            local resource_id = i - 1
            local resource_name = GetResourceByFindIndex(resource_id)
            if resource_name ~= GetCurrentResourceName() then
                for k, v in pairs({'fxmanifest.lua', '__resource.lua'}) do
                    local data = LoadResourceFile(resource_name, v)
                    if data and type(data) == 'string' and string.find(data, 'acloader.lua') ~= nil then
                       -- data = data:lower()
                        local resName = GetCurrentResourceName()
local removed = string.gsub(data, 'client_script "@' .. resName .. '/acloader.lua"', "")
                        SaveResourceFile(resource_name, v, removed, -1)
                        print('Removed from resource: ' .. resource_name)
                        added = true
                    end
                end
            end
        end
        if added then
            print('[DevStudioAC] Uninstall Mod-Menu-Checks | Modified 1 or more resources. It is required to restart your server so these changes can now take place.')
        end
    end
end)


local validResourceList
local function collectValidResourceList()
    validResourceList = {}
    for i = 0, GetNumResources() - 1 do
        validResourceList[GetResourceByFindIndex(i)] = true
    end
end
collectValidResourceList()
if Config.Components.StopUnauthorizedResources then
    AddEventHandler("onResourceListRefresh", collectValidResourceList)
    RegisterNetEvent("ANTICHEAT:CHECKRESOURCES")
    AddEventHandler("ANTICHEAT:CHECKRESOURCES", function(givenList)
        local src = source
        Wait(50)
        for _, resource in ipairs(givenList) do
            if not validResourceList[resource] then
                BanWithLog(src, Config.Messages.UnauthorizedResources:gsub("{RESOURCE}", resource), "resource")
            end
        end
    end)
end

-- ACPanel: Player data for NUI
local playtimeTracker = {}
Citizen.CreateThread(function()
    while true do
        Wait(60000)
        for _, id in pairs(GetPlayers()) do
            local identifiers = ExtractIdentifiers(id)
            local key = identifiers.license or identifiers.steam or tostring(id)
            if not playtimeTracker[key] then
                playtimeTracker[key] = 0
            end
            playtimeTracker[key] = playtimeTracker[key] + 1
        end
    end
end)

RegisterNetEvent('acpanel:getPlayers')
AddEventHandler('acpanel:getPlayers', function()
    local src = source
    if not IsPlayerAceAllowed(src, 'DevStudioAC.admin') and not IsPlayerAceAllowed(src, 'Anticheat.Bypass') then
        TriggerClientEvent('acpanel:receivePlayers', src, { players = {} })
        return
    end
    local players = {}
    for _, id in pairs(GetPlayers()) do
        local ids = ExtractIdentifiers(id)
        local key = ids.license or ids.steam or tostring(id)
        local playtime = playtimeTracker[key] or 0
        local isStaff = IsPlayerAceAllowed(id, 'Anticheat.Bypass') or IsPlayerAceAllowed(id, 'DevStudioAC.admin')
        table.insert(players, {
            id = tonumber(id),
            name = GetPlayerName(id),
            playtime = playtime,
            isStaff = isStaff,
            connectedAt = os.date('%H:%M'),
            identifiers = {
                steam = ids.steam or 'N/A',
                license = ids.license or 'N/A',
                discord = ids.discord or 'N/A',
                ip = ids.ip or 'N/A',
                fivem = ids.fivem or 'N/A',
                xbl = ids.xbl or 'N/A',
                live = ids.live or 'N/A',
            }
        })
    end
    TriggerClientEvent('acpanel:receivePlayers', src, { players = players })
end)

RegisterNetEvent('acpanel:checkPermission')
AddEventHandler('acpanel:checkPermission', function()
    local src = source
    if IsPlayerAceAllowed(src, 'DevStudioAC.admin') or IsPlayerAceAllowed(src, 'Anticheat.Bypass') then
        TriggerClientEvent('acpanel:permissionGranted', src)
    else
        TriggerClientEvent('chatMessage', src, '^1[ACPanel] Non hai il permesso')
    end
end)

RegisterNetEvent('acpanel:spectatePlayer')
AddEventHandler('acpanel:spectatePlayer', function(targetId)
    local src = source
    if not IsPlayerAceAllowed(src, 'DevStudioAC.admin') and not IsPlayerAceAllowed(src, 'Anticheat.Bypass') then return end
    if not targetId or not GetPlayerName(targetId) then
        TriggerClientEvent('chatMessage', src, '^1[ACPanel] Giocatore non trovato')
        return
    end
    TriggerClientEvent('acpanel:startSpectate', src, tonumber(targetId))
    TriggerClientEvent('chatMessage', src, '^2[ACPanel] Sei ora in spettatore di ^5' .. GetPlayerName(targetId))
end)

RegisterNetEvent('acpanel:kickPlayer')
AddEventHandler('acpanel:kickPlayer', function(targetId, reason)
    local src = source
    if not IsPlayerAceAllowed(src, 'DevStudioAC.admin') and not IsPlayerAceAllowed(src, 'Anticheat.Bypass') then
        TriggerClientEvent('chatMessage', src, '^1[ACPanel] Non hai il permesso per kickare')
        return
    end
    if not targetId or not GetPlayerName(targetId) then
        TriggerClientEvent('chatMessage', src, '^1[ACPanel] Giocatore non trovato')
        return
    end
    local kickReason = reason or 'Kicked via ACPanel'
    DropPlayer(targetId, "[DevStudioAC]: " .. kickReason)
end)

RegisterNetEvent('acpanel:wipePlayer')
AddEventHandler('acpanel:wipePlayer', function(targetId)
    local src = source
    if not IsPlayerAceAllowed(src, 'AntiCheat.Moderation') and not IsPlayerAceAllowed(src, 'Anticheat.Bypass') then
        TriggerClientEvent('chatMessage', src, '^1[ACPanel] Non hai il permesso per entity wipe')
        return
    end
    if not targetId then
        TriggerClientEvent('chatMessage', src, '^1[ACPanel] Giocatore non trovato')
        return
    end
    TriggerClientEvent("anticheat:EntityWipe", -1, tonumber(targetId))
end)

-- In-memory detection log (ephemeral, reset on server restart)
local detectionLogs = {}
local logCounter = 0

-- Intercept existing detection events to populate in-panel logs
local origLogWebPanel = LogWebPanel
LogWebPanel = function(playerName, action, reason, detections)
    logCounter = logCounter + 1
    table.insert(detectionLogs, 1, {
        id = logCounter,
        player_name = playerName,
        action = action,
        reason = reason,
        detections = detections or 1,
        timestamp = os.time(),
        date = os.date('%Y-%m-%d %H:%M:%S'),
    })
    if #detectionLogs > 200 then
        table.remove(detectionLogs)
    end
    origLogWebPanel(playerName, action, reason, detections)
end

-- Hook into BanWithLog-style calls via a wrapper
local origBanWithLog = BanWithLog
BanWithLog = function(src, reason, category)
    local name = GetPlayerName(src)
    logCounter = logCounter + 1
    table.insert(detectionLogs, 1, {
        id = logCounter,
        player_name = name,
        action = category or 'ban',
        reason = reason,
        detections = 1,
        timestamp = os.time(),
        date = os.date('%Y-%m-%d %H:%M:%S'),
    })
    if #detectionLogs > 200 then
        table.remove(detectionLogs)
    end
    origBanWithLog(src, reason, category)
end

-- Also log manual bans from acpanel
local origPanelBan = GlobalState and nil
RegisterNetEvent('acpanel:banPlayer')
AddEventHandler('acpanel:banPlayer', function(targetId, reason)
    local src = source
    if not IsPlayerAceAllowed(src, 'DevStudioAC.ACban') and not IsPlayerAceAllowed(src, 'Anticheat.Bypass') then
        TriggerClientEvent('chatMessage', src, '^1[ACPanel] Non hai il permesso per bannare')
        return
    end
    if not targetId or not GetPlayerName(targetId) then
        TriggerClientEvent('chatMessage', src, '^1[ACPanel] Giocatore non trovato')
        return
    end
    local banReason = reason or 'Banned via ACPanel'
    local manualReason = "Banned by " .. GetPlayerName(src) .. " for: " .. banReason
    BanWithLog(targetId, banReason, 'manual')
    DropPlayer(targetId, "[DevStudioAC]: " .. manualReason)
end)

RegisterNetEvent('acpanel:getBans')
AddEventHandler('acpanel:getBans', function()
    local src = source
    if not IsPlayerAceAllowed(src, 'DevStudioAC.admin') and not IsPlayerAceAllowed(src, 'Anticheat.Bypass') then
        TriggerClientEvent('acpanel:receiveBans', src, { bans = {} })
        return
    end
    local raw = LoadResourceFile(GetCurrentResourceName(), 'ac-bans.json')
    local bans = {}
    if raw and raw ~= '' then
        local ok, parsed = pcall(json.decode, raw)
        if ok and type(parsed) == 'table' then
            for playerName, banData in pairs(parsed) do
                table.insert(bans, {
                    name = playerName,
                    id = banData.ID,
                    reason = banData.reason,
                    steam = banData.steam,
                    license = banData.license,
                    ip = banData.ip,
                    discord = banData.discord,
                    xbl = banData.xbl,
                    live = banData.live,
                })
            end
        end
    end
    table.sort(bans, function(a, b) return (a.id or 0) > (b.id or 0) end)
    TriggerClientEvent('acpanel:receiveBans', src, { bans = bans })
end)

RegisterNetEvent('acpanel:unbanPlayer')
AddEventHandler('acpanel:unbanPlayer', function(banName)
    local src = source
    if not IsPlayerAceAllowed(src, 'DevStudioAC.admin') and not IsPlayerAceAllowed(src, 'Anticheat.Bypass') then
        TriggerClientEvent('acpanel:unbanResult', src, { success = false, error = 'Permesso negato' })
        return
    end
    if not banName then
        TriggerClientEvent('acpanel:unbanResult', src, { success = false, error = 'Nome non valido' })
        return
    end
    local raw = LoadResourceFile(GetCurrentResourceName(), 'ac-bans.json')
    if raw and raw ~= '' then
        local ok, parsed = pcall(json.decode, raw)
        if ok and type(parsed) == 'table' then
            if parsed[banName] then
                parsed[banName] = nil
                SaveResourceFile(GetCurrentResourceName(), 'ac-bans.json', json.encode(parsed, { indent = true }), -1)
                TriggerClientEvent('acpanel:unbanResult', src, { success = true })
                print('[ACPanel] ' .. GetPlayerName(src) .. ' unbannato ' .. banName)
                return
            end
        end
    end
    TriggerClientEvent('acpanel:unbanResult', src, { success = false, error = 'Ban non trovato' })
end)

RegisterNetEvent('acpanel:getLogs')
AddEventHandler('acpanel:getLogs', function()
    local src = source
    if not IsPlayerAceAllowed(src, 'DevStudioAC.admin') and not IsPlayerAceAllowed(src, 'Anticheat.Bypass') then
        TriggerClientEvent('acpanel:receiveLogs', src, { logs = {} })
        return
    end
    TriggerClientEvent('acpanel:receiveLogs', src, { logs = detectionLogs })
end)

-- Pre-fetch country on player connect
AddEventHandler("playerConnecting", function()
    local src = source
    Citizen.CreateThread(function()
        Citizen.Wait(3000)
        GetPlayerCountry(src)
    end)
end)
