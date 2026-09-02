#!/usr/bin/env python3
"""Quita del validador de Fleet las llaves de kiosko Android.

Fleet rechaza al SUBIR un perfil Android que traiga kioskCustomLauncherEnabled,
kioskCustomization o persistentPreferredActivities
(server/fleet/android.go -> AndroidForbiddenJSONKeys), con el mensaje
"Currently, only personal hosts are supported."

No es un muro de pago ni un límite de Google: el field mask con el que Fleet le parcha
la política a Google (server/mdm/android/service/androidmgmt/google_client.go) YA incluye
esas tres llaves, y el reconciliador manda el JSON crudo del perfil sin volver a validarlo.
El freno está sólo en el validador de subida. Esto lo quita.

NO se toca "applications": Fleet parcha las apps por separado
(EnterprisesPoliciesModifyPolicyApplications, con el mask "applications") y su patch normal
las excluye a propósito (PoliciesPatchOpts{ExcludeApps: true}), así que una lista de apps en
un perfil no llegaría a Google y encima pelearía con la app-agente de Fleet.
El APK del BackOffice se mete por `adb install` y se vuelve HOME con
persistentPreferredActivities.

Uso: allow_android_kiosk_keys.py <ruta a server/fleet/android.go>
Falla con código 1 si no encuentra qué quitar (para que el build truene, no para que
pase de largo con un binario sin parchar).
"""
import re
import sys

KEYS = [
    "kioskCustomLauncherEnabled",
    "kioskCustomization",
    "persistentPreferredActivities",
]

path = sys.argv[1]
src = open(path, encoding="utf-8").read()

start = src.find("var AndroidForbiddenJSONKeys = map[string]string{")
if start == -1:
    sys.exit("ERROR: no encontré AndroidForbiddenJSONKeys en %s" % path)
end = src.find("\n}\n", start)
if end == -1:
    sys.exit("ERROR: no encontré el cierre del mapa AndroidForbiddenJSONKeys")

block = src[start:end]
new_block = block
for key in KEYS:
    # la entrada es una línea completa:  "<key>": `...`,
    pattern = re.compile(r'^\t"%s":.*\n' % re.escape(key), re.MULTILINE)
    new_block, n = pattern.subn("", new_block)
    if n != 1:
        sys.exit('ERROR: esperaba 1 entrada de "%s" en el mapa, encontré %d' % (key, n))

src = src[:start] + new_block + src[end:]
open(path, "w", encoding="utf-8").write(src)

# verificación dura: las llaves ya no pueden estar en el mapa
block_after = src[src.find("var AndroidForbiddenJSONKeys"):]
block_after = block_after[: block_after.find("\n}\n")]
for key in KEYS:
    if key in block_after:
        sys.exit('ERROR: "%s" sigue en el mapa después del parche' % key)

print("Parche aplicado: %s liberadas en %s" % (", ".join(KEYS), path))
