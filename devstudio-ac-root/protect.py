import os, re, json, hashlib, random, string, shutil, io, zipfile, base64
from datetime import datetime

AC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'devstudio_anticheat_custom')
BUILD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build')
SECRET = os.environ.get('HMAC_SECRET', 'DsAcHmac!7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f')

ALL_PROTECTED = ['client.lua', 'acloader.lua', 'Enumerators.lua', 'server.lua', 'config.lua', 'sha256.lua']
PLAIN_COPY = ['fxmanifest.lua', 'licenses.json', 'ac-bans.json', 'README.md', 'LICENSE']
SERVER_NAMES = {'server.lua', 'config.lua', 'sha256.lua'}
CLIENT_NAMES = {'client.lua', 'acloader.lua', 'Enumerators.lua'}

KEYWORDS = {
    'if', 'then', 'else', 'elseif', 'end', 'while', 'do', 'for', 'in',
    'repeat', 'until', 'function', 'return', 'local', 'nil', 'true',
    'false', 'not', 'and', 'or', 'break', 'goto', 'Citizen', 'Wait',
}

def random_name(length=None):
    if not length: length = random.randint(10, 24)
    return '_' + ''.join(random.choices(string.ascii_letters, k=length))

def xor_encrypt(data, key):
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

def encrypt_strings(code):
    strings = set(re.findall(r'"([^"]*)"', code))
    strings |= set(re.findall(r"'([^']*)'", code))
    key = bytes(random.choices(range(1, 256), k=16))
    key_b64 = base64.b64encode(key).decode()
    dn = random_name(16)
    dec = (
        f'local function {dn}(s,k)\n'
        f' local r={{}};local sk=base64.decode(k)\n'
        f' for i=1,#s do r[i]=string.char(string.byte(s,i)~=sk[((i-1)%#sk)+1]) end\n'
        f' return table.concat(r)\n'
        f'end\n'
    )
    for s in sorted(strings, key=len, reverse=True):
        if len(s) < 3 or s in ('', ' '): continue
        enc = base64.b64encode(xor_encrypt(s.encode(), key)).decode()
        code = code.replace(f'"{s}"', f'({dn}("{enc}","{key_b64}"))')
        code = code.replace(f"'{s}'", f'({dn}("{enc}","{key_b64}"))')
    code = dec + code
    return code

def obfuscate_lua(code):
    for line in code.split('\n'):
        line = re.sub(r'--\[\[.*?\]\]', '', line, flags=re.DOTALL)
        line = re.sub(r'--[^\n]*', '', line)
    code = '\n'.join([re.sub(r'--\[\[.*?\]\]', '', l, flags=re.DOTALL) or re.sub(r'--[^\n]*', '', l) for l in code.split('\n')])
    code = re.sub(r'--\[\[.*?\]\]', '', code, flags=re.DOTALL)
    code = re.sub(r'--[^\n]*', '', code)

    code = encrypt_strings(code)

    func_names = set(re.findall(r'(?<=function\s)(\w+)', code))
    local_vars = set(re.findall(r'(?:local\s+)(\w+)', code))
    param_vars = set()
    for m in re.findall(r'function\s+\w+\(([^)]*)\)', code):
        for p in m.split(','):
            p = p.strip()
            if p and p != '...': param_vars.add(p)

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
        'DeleteEntity', 'GetEntityPlayerIsFreeAimingAt', 'GetPlayerServerId',
        'GetGameplayCamRot', 'GetGameplayCamCoord', 'GetShapeTestResult',
        'StartShapeTestCapsule', 'World3dToScreen2d', 'SetTextScale',
        'SetTextFont', 'SetTextProportional', 'SetTextColour', 'SetTextOutline',
        'SetTextEntry', 'AddTextComponentString', 'DrawText', 'SetTextCentre',
        'GetNumResources', 'GetResourceByFindIndex', 'CreateThread', 'GetPlayerName',
        'NetworkGetEntityOwner', 'GetEntityPopulationType', 'IsPedAPlayer',
        'IsEntityAPed', 'IsPedModel', 'GetAllEnumerators', 'EnumerateObjects',
        'EnumeratePeds', 'EnumerateVehicles', 'EnumeratePickups',
        'PerformHttpRequest', 'LoadResourceFile', 'SaveResourceFile',
        'GetCurrentResourceName', 'DropPlayer', 'GetPlayers', 'GetPlayerPed',
        'GetEntityCoords', 'IsPlayerAceAllowed', 'CancelEvent', 'RegisterCommand',
        'GetNumPlayerIdentifiers', 'GetPlayerIdentifier',
        'json', 'table', 'string', 'math', 'pairs', 'ipairs', 'pcall',
        'tostring', 'tonumber', 'type', 'next', 'unpack', 'select',
        'SetTimeout', 'print', 'base64', 'sha256',
    }

    api_funcs = {n for n in func_names if n[0].isupper() or n in known_api}
    local_vars = {v for v in local_vars if not (v[0].isupper() or v in known_api)}
    param_vars = {v for v in param_vars if not (v[0].isupper() or v in known_api)}
    func_names = {n for n in func_names if n not in api_funcs}

    var_map = {}
    for var in func_names | local_vars | param_vars:
        if var in KEYWORDS or var in known_api: continue
        n = random_name()
        while n in var_map.values() or n in known_api: n = random_name()
        var_map[var] = n

    lines = []
    for line in code.split('\n'):
        line = re.sub(r'--\[\[.*?\]\]', '', line)
        line = re.sub(r'--[^\n]*', '', line)
        tokens = re.split(r'(\W)', line)
        for i, t in enumerate(tokens):
            if t in var_map: tokens[i] = var_map[t]
        lines.append(''.join(tokens))
    code = '\n'.join(lines)
    code = re.sub(r'\n\s*\n', '\n', code)
    code = re.sub(r'^\s*\n', '', code, flags=re.MULTILINE)
    return code.strip()

def to_hex_escaped(data):
    parts = []
    for b in data:
        parts.append(f'\\x{b:02x}')
    return ''.join(parts)

def make_loader(fname, xor_key, full_encrypted):
    sig = hashlib.sha256(SECRET.encode() + fname.encode())
    expected_hash = sig.hexdigest()[:16]

    hex_blob = to_hex_escaped(full_encrypted)
    hex_key = to_hex_escaped(xor_key)

    line = 'load((function(s,k)local r={}for i=1,#s do r[i]=string.char(string.byte(s,i)~=k:byte(((i-1)%#k)+1))end return table.concat(r)end)'
    line += f'("{hex_blob}","{hex_key}"))()'

    return line + '\n', expected_hash

def make_guard_code(fname):
    sentinel_seed = SECRET + '_guard_'
    sentinel_value = hashlib.sha256((sentinel_seed + fname).encode()).hexdigest()
    guard_key = hashlib.sha256((SECRET + fname + '_guard_key').encode()).hexdigest()[:8]
    alt_seed = int(hashlib.sha256((SECRET+fname+"alt").encode()).hexdigest()[:2], 16)

    g = 'do local _k="' + guard_key + '"\n'
    g += 'local _s={"_init",function()\n'
    g += ' local _g={{"' + sentinel_value + '"}}\n'
    g += ' local _c=_G.Citizen\n'
    g += ' if _c and _c.CreateThread then\n'
    g += '  _c.CreateThread(function()\n'
    g += '   while true do\n'
    g += '    _c.Wait(' + str(15000+alt_seed) + ')\n'
    g += '    if _g[1]~="' + sentinel_value + '" then\n'
    g += '     _G.TriggerServerEvent("Anticheat:Modder","TAMPER","' + fname + ' modified")\n'
    g += '     _g[1]="' + sentinel_value + '"\n'
    g += '    end\n'
    g += '   end\n'
    g += '  end)\n'
    g += '  _c.CreateThread(function()\n'
    g += '   while true do\n'
    g += '    _c.Wait(' + str(30000+alt_seed) + ')\n'
    g += '    local _h=sha256 and sha256.hmac or nil\n'
    g += '    if not _h then\n'
    g += '     _G.TriggerServerEvent("Anticheat:Modder","TAMPER","sha256 removed")\n'
    g += '    end\n'
    g += '   end\n'
    g += '  end)\n'
    g += ' end\n'
    g += 'end}\n_s[1](_s)\nend\n'
    return g

def create_build():
    if os.path.exists(BUILD_PATH):
        shutil.rmtree(BUILD_PATH)
    os.makedirs(BUILD_PATH, exist_ok=True)

    final_hashes = {}

    for fname in ALL_PROTECTED:
        src = os.path.join(AC_PATH, fname)
        if not os.path.exists(src):
            print(f"SKIP {fname} not found")
            continue

        code = open(src, 'r', encoding='utf-8').read()
        obfuscated = obfuscate_lua(code)
        guard_code = make_guard_code(fname)
        combined = guard_code + obfuscated

        xor_key = bytes(random.choices(range(1, 256), k=16))
        encrypted = xor_encrypt(combined.encode('utf-8'), xor_key)

        loader, expected_hash = make_loader(fname, xor_key, encrypted)
        final_hashes[fname] = expected_hash

        dst = os.path.join(BUILD_PATH, fname)
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(loader)
        print(f"Protected: {fname} ({len(combined)}B -> {len(encrypted)}B encrypted)")

    for f in PLAIN_COPY:
        src = os.path.join(AC_PATH, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(BUILD_PATH, f))
            print(f"Copied: {f}")

    integrity_path = os.path.join(BUILD_PATH, 'integrity.json')
    with open(integrity_path, 'w') as f:
        json.dump(final_hashes, f, indent=2)

    print(f"Build created in: {BUILD_PATH}")
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
