#!/usr/bin/env python3
"""Fleet manda su agente Android (com.fleetdm.agent) SIN el rol COMPANION_APP.

Por qué: AMAPI deja que UNA sola app tenga el rol COMPANION_APP, y es el que necesita nuestro
«Reno Actualizador» (com.renopartes.actualizador) para pedirle a Android Device Policy que instale
nuestros APK sin Play (InstallCustomApp). Fleet se lo pone a su agente en
buildFleetAgentAppPolicy (server/mdm/android/service/service.go) y lo vuelve a mandar cuando un host
cambia de team o hay certificados pendientes. Entre dos llamadas distintas Google no rechaza: se
queda con la última y le QUITA el rol al actualizador sin avisar (medido el 2026-10-14 en el
RZGL31WJ40E). Decisión del Usuario 2026-10-14 (#47670): opción (a), parchar el rol y dejar el agente.

Qué cambia: sólo se quita el bloque `Roles` de esa función. El agente sigue instalado
(FORCE_INSTALLED) y con su managedConfiguration, su CERT_INSTALL y su firma; sirve para
certificados SCEP, que Reno no usa. Sin el rol pierde la exención de batería y el arranque por
"aviso de roles" al instalarse; según su README también arranca con BOOT_COMPLETED y cada 15 min.

Uso: android_agent_sin_companion.py <server/mdm/android/service/service.go>
Falla con código 1 si no encuentra el bloque (para que el build truene, no para que pase de largo
con un binario sin parchar).
"""
import sys

ROLES = """		Roles: []*androidmanagement.Role{
			{
				RoleType: "COMPANION_APP",
			},
		},
"""

path = sys.argv[1]
src = open(path, encoding="utf-8").read()

start = src.find("func buildFleetAgentAppPolicy(")
if start == -1:
    sys.exit("ERROR: no encontré buildFleetAgentAppPolicy en %s" % path)
end = src.find("\n}\n", start)
func = src[start:end]
if func.count(ROLES) != 1:
    sys.exit("ERROR: esperaba 1 bloque Roles COMPANION_APP en buildFleetAgentAppPolicy, encontré %d"
             % func.count(ROLES))

nuevo = func.replace(ROLES, "\t\t// [Reno] Sin rol de compañera: es del Reno Actualizador (ver patches/).\n")
src = src[:start] + nuevo + src[end:]
open(path, "w", encoding="utf-8").write(src)

# verificación dura
func_after = src[src.find("func buildFleetAgentAppPolicy("):]
func_after = func_after[: func_after.find("\n}\n")]
if "COMPANION_APP" in func_after or "Roles:" in func_after:
    sys.exit("ERROR: el agente sigue llevando roles después del parche")
print("Parche aplicado: agente de Fleet sin rol COMPANION_APP en %s" % path)
