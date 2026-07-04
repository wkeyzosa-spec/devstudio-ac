import os, re, json, hashlib, random, string, shutil, io, zipfile
from datetime import datetime

AC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build')
BUILD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build')
SECRET = "DsAc2024S3cur3K3y!@#$"

CLIENT_FILES = ['client.lua', 'acloader.lua', 'Enumerators.lua']
SHARED_FILES = ['config.lua', 'sha256.lua']
SERVER_FILES = ['server.lua']

KEYWORDS = {
    'if', 'then', 'else', 'elseif', 'end', 'while', 'do', 'for', 'in',
    'repeat', 'until', 'function', 'return', 'local', 'nil', 'true',
    'false', 'not', 'and', 'or', 'break', 'goto', 'Citizen', 'Wait',
}

def random_name():
    return '_' + ''.join(random.choices(string.ascii_letters, k=random.randint(8, 16)))

def obfuscate_lua(code):
    lines = code.split('\n')
    cleaned = []
    for line in lines:
        line = re.sub(r'--\[\[.*?\]\]', '', line, flags=re.DOTALL)
        line = re.sub(r'--[^\n]*', '', line)
        cleaned.append(line)
    code = '\n'.join(cleaned)

    func_names = set(re.findall(r'(?<=function\s)(\w+)', code))
    local_vars = set(re.findall(r'(?:local\s+)(\w+)', code))
    param_vars = set()
    func_defs = re.findall(r'function\s+\w+\(([^)]*)\)', code)
    for params in func_defs:
        for p in params.split(','):
            p = p.strip()
            if p and p != '...':
                param_vars.add(p)

    globals_found = set(re.findall(r'(?<![.\w])(\w+)(?=\s*[=(])', code))
    known_api = {
        'Config', 'TriggerServerEvent', 'TriggerClientEvent', 'RegisterNetEvent',
        'AddEventHandler', 'Citizen', 'Wait', 'PlayerPedId', 'GetEntityCoords',
        'IsPedStill', 'GetEntitySpeed', 'NetworkIsInSpectatorMode',
        'GetEntityHealth', 'GetPedArmour', 'GetEntityMaxHealth', 'SetEntityHealth',
        'SetPedArmour', 'SetPedInfiniteAmmoClip', 'SetEntityInvincible',
        'SetEntityCanBeDamaged', 'ResetEntityAlpha', 'IsPedFalling',
        'IsPedRagdoll', 'GetPedParachuteState', 'SetEntityMaxSpeed',
        'GetRegisteredCommands', 'IsDisabledControlJustReleased',
        'IsDisabledControlPressed', 'GetPlayerPed', 'GetSelectedPedWeapon',
        'GetHashKey', 'DoesEntityExist', 'NetworkGetEntityOwner',
        'GetEntityType', 'GetEntityPopulationType', 'GetEntityModel',
        'RequestControlOfEntity', 'NetworkHasControlOfEntity',
        'NetworkRequestControlOfEntity', 'DetachEntity', 'SetEntityCollision',
        'SetEntityAlpha', 'SetEntityAsMissionEntity', 'SetEntityAsNoLongerNeeded',
        'DeleteEntity', 'GetEntityPlayerIsFreeAimingAt',
        'GetPlayerServerId', 'GetGameplayCamRot', 'GetGameplayCamCoord',
        'GetShapeTestResult', 'StartShapeTestCapsule',
        'World3dToScreen2d', 'SetTextScale', 'SetTextFont',
        'SetTextProportional', 'SetTextColour', 'SetTextOutline',
        'SetTextEntry', 'AddTextComponentString', 'DrawText',
        'SetTextCentre', 'GetNumResources', 'GetResourceByFindIndex',
        'CreateThread', 'GetPlayerName', 'NetworkGetEntityOwner',
        'GetEntityPopulationType', 'NetworkGetEntityOwner',
        'IsPedAPlayer', 'IsEntityAPed', 'IsPedModel',
        'GetAllEnumerators', 'EnumerateObjects', 'EnumeratePeds',
        'EnumerateVehicles', 'EnumeratePickups',
    }

    api_funcs = set()
    for name in func_names:
        if name[0].isupper() or name in known_api:
            api_funcs.add(name)

    for v in list(local_vars):
        if v[0].isupper() or v in known_api:
            local_vars.discard(v)

    for v in list(param_vars):
        if v[0].isupper() or v in known_api:
            param_vars.discard(v)

    for v in list(func_names - api_funcs):
        if v in known_api:
            api_funcs.add(v)
        if v[0].isupper():
            api_funcs.add(v)

    var_map = {}
    all_rename = (func_names - api_funcs) | local_vars | param_vars
    for var in all_rename:
        if var in KEYWORDS or var in known_api:
            continue
        n = random_name()
        while n in var_map.values():
            n = random_name()
        var_map[var] = n

    lines = []
    for line in code.split('\n'):
        original = line

        line = re.sub(r'--\[\[.*?\]\]', '', line)
        line = re.sub(r'--[^\n]*', '', line)

        tokens = re.split(r'(\W)', line)
        for i, t in enumerate(tokens):
            if t in var_map:
                tokens[i] = var_map[t]
        line = ''.join(tokens)
        lines.append(line)

    code = '\n'.join(lines)

    code = re.sub(r'\n\s*\n', '\n', code)
    code = re.sub(r'^\s*\n', '', code, flags=re.MULTILINE)
    code = code.strip()

    return code

def compute_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()

def create_build():
    if os.path.exists(BUILD_PATH):
        shutil.rmtree(BUILD_PATH)
    os.makedirs(BUILD_PATH, exist_ok=True)

    integrity = {}

    for fname in CLIENT_FILES:
        src = os.path.join(AC_PATH, fname)
        code = open(src, 'r', encoding='utf-8').read()

        sig = hashlib.sha256(SECRET.encode())
        sig.update(code.encode())
        expected_hash = sig.hexdigest()[:16]

        obfuscated = obfuscate_lua(code)
        sentinel = hashlib.sha256((SECRET + '_guard_' + fname).encode()).hexdigest()
        guard = f"""--[[ DSAC-PROTECTED ]]
do
 local _g={{"{sentinel}"}}
 local _c=_G.Citizen
 if _c and _c.CreateThread then
  _c.CreateThread(function()
   while true do
    _c.Wait(30000)
    if _g[1]~="{sentinel}" then
     _G.TriggerServerEvent("Anticheat:Modder","TAMPER","Protected file modified")
     _g[1]="{sentinel}"
    end
   end
  end)
 end
end

"""
        final = guard + obfuscated
        dst = os.path.join(BUILD_PATH, fname)
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(final)

        integrity[fname] = expected_hash

    for fname in SHARED_FILES + SERVER_FILES:
        src = os.path.join(AC_PATH, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(BUILD_PATH, fname))

    for f in ['fxmanifest.lua', 'licenses.json', 'ac-bans.json', 'README.md', 'LICENSE']:
        src = os.path.join(AC_PATH, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(BUILD_PATH, f))

    integrity_path = os.path.join(BUILD_PATH, 'integrity.json')
    with open(integrity_path, 'w') as f:
        json.dump(integrity, f, indent=2)

    print(f"Build created in: {BUILD_PATH}")
    print(f"Protected files: {', '.join(CLIENT_FILES)}")
    return BUILD_PATH

def create_zip():
    zip_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BUILD_PATH):
            for f in files:
                fp = os.path.join(root, f)
                zf.write(fp, os.path.relpath(fp, BUILD_PATH))
    print(f"Zip created: {zip_path}")
    return zip_path

if __name__ == '__main__':
    create_build()
    create_zip()
    print("Protection complete.")
