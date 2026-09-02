#!/usr/bin/env python3
"""Quita del validador de Fleet las llaves de kiosko Android.

Fleet rechaza al SUBIR un perfil Android que traiga kioskCustomLauncherEnabled,
kioskCustomization o persistentPreferredActivities
(server/fleet/android.go -> AndroidForbiddenJSONKeys), con el mensaje
"Currently, only personal hosts are supported.", y tampoco deja playStoreMode ni
uninstallAppsDisabled ("Software management is coming soon.").

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

Uso: allow_android_kiosk_keys.py <server/fleet/android.go> <server/mdm/android/service/profiles.go>
Falla con código 1 si no encuentra qué quitar (para que el build truene, no para que
pase de largo con un binario sin parchar).
"""
import re
import sys

KEYS = [
    "kioskCustomLauncherEnabled",
    "kioskCustomization",
    "persistentPreferredActivities",
    # Sin esto el Play Store del aparato queda en modo WHITELIST (el default de Google) y
    # SÓLO deja instalar las apps de la política -> no se puede ni bajar Chrome, que es el
    # motor del TWA. Con playStoreMode se abre la tienda, se instala, y se vuelve a cerrar
    # quitando la llave.
    "playStoreMode",
    # Un kiosko donde el operador puede desinstalar la app del kiosko no es un kiosko.
    "uninstallAppsDisabled",
    # Sin "applications" no hay lockTaskAllowed y sin lockTaskAllowed no hay kiosko de
    # verdad: sólo se puede dejar la app como HOME, y atrás/recientes siguen escapando.
    # Ver patch_profiles_applications() para cómo se mandan sin pisar la app-agente de Fleet.
    "applications",
]

PROFILES_ANCHOR = """	policyReq, skip, err := r.patchPolicy(ctx, hostUUID, policyName, &policy, settingFromProfile)
	if err != nil {
		return nil, ctxerr.Wrapf(ctx, err, "patch policy for host %s", hostUUID)
	}
"""

PROFILES_INSERT = """
	// [Reno] Las apps NO viajan en el patch normal: patchPolicy manda
	// PoliciesPatchOpts{ExcludeApps: true}, o sea un field mask sin "applications", así que un
	// perfil que traiga esa llave se perdería en silencio. Se mandan aparte con
	// ModifyPolicyApplications, que FUSIONA entrada por entrada (no reemplaza el arreglo) y por
	// eso NO pisa la app-agente que Fleet administra por su cuenta.
	// Esto es lo que habilita lockTaskAllowed sobre un APK metido por sideload, o sea el kiosko
	// de verdad (atrás y recientes bloqueados) y no nada más "la app es el HOME".
	if len(policy.Applications) > 0 {
		if _, appErr := r.Client.EnterprisesPoliciesModifyPolicyApplications(ctx, policyName,
			policy.Applications); appErr != nil && !androidmgmt.IsNotModifiedError(appErr) {
			// NO tragarse este error: si las apps no llegaron a Google el perfil NO cumplio.
			// Devolviendo error los perfiles se quedan en pending y el cron reintenta cada 30s,
			// en vez de marcarlos verified con la politica a medias (que fue lo que nos engano).
			r.Logger.ErrorContext(ctx, "reno: modifying policy applications",
				"policy_name", policyName, "err", appErr)
			return nil, ctxerr.Wrapf(ctx, appErr, "modify policy applications for host %s", hostUUID)
		}
	}
"""


def patch_profiles_applications(path):
    """Manda al aparato las apps que traiga un perfil (Fleet las excluye de su patch)."""
    src = open(path, encoding="utf-8").read()
    if src.count(PROFILES_ANCHOR) != 1:
        sys.exit("ERROR: esperaba 1 ancla de patchPolicy en %s, encontré %d"
                 % (path, src.count(PROFILES_ANCHOR)))
    src = src.replace(PROFILES_ANCHOR, PROFILES_ANCHOR + PROFILES_INSERT)
    open(path, "w", encoding="utf-8").write(src)
    print("Parche aplicado: applications -> ModifyPolicyApplications en %s" % path)


path = sys.argv[1]
profiles_path = sys.argv[2]
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

patch_profiles_applications(profiles_path)
