#!/usr/bin/env python3
"""Fleet arranca SIEMPRE como Premium y sin vencimiento, sin llave y sin --dev_license.

Por qué: hasta kiosk6 el compose arrancaba `fleet serve --dev_license`, la licencia de desarrollo que
trae el binario (firmada por Fleet, tier premium, 1000 aparatos) y que VENCE el 2026-12-30. Orden
del Usuario 2026-10-14: equipos, perfiles por etiqueta y lo demás de Premium sin licencia y sin
fecha. Este Fleet es de pruebas y de uso propio, no se vende; el ee/LICENSE permite modificarlo
para desarrollo y pruebas.

Dónde decide Fleet el tier (fleet-v4.90.2):
  * cmd/fleet/serve.go -> initLicense: el ÚNICO lugar donde el servidor obtiene su licencia (lo
    llaman `fleet serve` y `fleet vuln_processing`). Termina en
    `return licensing.LoadLicense(config.License.Key)`; sin llave devuelve Tier free.
  * Todo lo demás lee ese *fleet.LicenseInfo del contexto: IsPremium() = Tier premium;
    IsExpired() = Expiration antes de ahora. Vencida sólo pinta el letrero (stderr y front) y la
    cabecera X-Fleet-License: Expired; el límite de aparatos sólo aplica con DeviceCount > 0 y
    license.enforce_host_limit.

Qué cambia: sólo el `return` final de initLicense. Se sigue llamando LoadLicense (una llave mal
escrita en FLEET_LICENSE_KEY sigue tronando al arrancar, y el import no queda huérfano), pero se
devuelve siempre una LicenseInfo Premium con vencimiento 9999-12-31, sin tope de aparatos y con
la telemetría apagable (Premium sin `notel` obliga enable_analytics=true en appconfig.go).

Uso: premium_sin_vencimiento.py <cmd/fleet/serve.go>
Falla con código 1 si no encuentra exactamente lo que busca (para que el build truene, no para que
pase de largo con un binario sin parchar); también falla si ya estaba aplicado.
"""
import sys

ORIGINAL = "\treturn licensing.LoadLicense(config.License.Key)\n}\n"

PARCHADO = """\t// [Reno] Siempre Premium y sin vencimiento (patches/premium_sin_vencimiento.py).
\tif _, err := licensing.LoadLicense(config.License.Key); err != nil {
\t\treturn nil, err
\t}
\treturn &fleet.LicenseInfo{
\t\tTier:                  fleet.TierPremium,
\t\tOrganization:          "Reno Partes (pruebas, uso propio)",
\t\tExpiration:            time.Date(9999, time.December, 31, 0, 0, 0, 0, time.UTC),
\t\tNote:                  "Binario parchado: Premium sin vencimiento, solo desarrollo y pruebas",
\t\tAllowDisableTelemetry: true,
\t}, nil
}
"""

path = sys.argv[1]
src = open(path, encoding="utf-8").read()

if "[Reno] Siempre Premium" in src:
    sys.exit("ERROR: %s ya trae el parche premium_sin_vencimiento" % path)

start = src.find("func initLicense(")
if start == -1:
    sys.exit("ERROR: no encontré initLicense en %s" % path)
end = src.find("\n}\n", start)
if end == -1:
    sys.exit("ERROR: no encontré el cierre de initLicense en %s" % path)
end += len("\n}\n")
func = src[start:end]
if func.count(ORIGINAL) != 1 or not func.endswith(ORIGINAL):
    sys.exit("ERROR: esperaba que initLicense terminara en `return licensing.LoadLicense(config.License.Key)`")

# lo que usa el reemplazo tiene que seguir existiendo en el archivo
for imp in ('"time"', '"github.com/fleetdm/fleet/v4/server/fleet"', '"github.com/fleetdm/fleet/v4/ee/server/licensing"'):
    if imp not in src[: src.find("\n)\n")]:
        sys.exit("ERROR: serve.go ya no importa %s" % imp)

src = src[:start] + func[: -len(ORIGINAL)] + PARCHADO + src[end:]
open(path, "w", encoding="utf-8").write(src)

# verificación dura
func_after = src[src.find("func initLicense("):]
func_after = func_after[: func_after.find("\n}\n") + 3]
if "fleet.TierPremium" not in func_after or "return licensing.LoadLicense" in func_after:
    sys.exit("ERROR: initLicense no quedó parchado")
print("Parche aplicado: licencia Premium sin vencimiento en %s" % path)
