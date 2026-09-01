# Fleet en Coolify (Reno Partes)

MDM autohospedado para la **flota de iPads** (kiosko del BackOffice). Es
[Fleet](https://github.com/fleetdm/fleet), MIT en el core.

> Las tablets **Android siguen en MDMesh**. En Fleet, el modo *fully-managed / device owner* de
> Android es Premium ($7 por aparato al mes), así que no tiene caso mover lo que ya funciona.

## Dónde vive

- Consola: `https://fleet.renopartes.com`
- Coolify: proyecto *Reno Partes* / production, recurso `fleet`
- Puerto en el host: **6793** → el túnel de Cloudflare enruta `fleet.renopartes.com → localhost:6793`

⚠️ El servidor **no tiene puertos inbound abiertos**: todo entra por el túnel. Dar de alta el
dominio en Coolify sin su entrada en el túnel no sirve de nada.

## Por qué Fleet y no otro

1. **Fleet firma su propio CSR: es vendor MDM registrado ante Apple.** Se baja el CSR desde la
   consola, se sube a `identity.apple.com` y se regresa el `.pem`. **Sin `mdmcert.download`, sin
   D-U-N-S, sin Apple Business.** Apple Business sólo hace falta para zero-touch (Premium).
2. El perfil de enrolamiento trae **`SignMessage: <true/>`**
   (`server/mdm/apple/apple_mdm.go`), o sea el check-in de los aparatos va firmado por header
   `Mdm-Signature` y **no por TLS mutuo** → **pasa por el túnel de Cloudflare**. Con mTLS el túnel
   lo habría roto y no habría deploy posible en este server.

## Qué cabe en el tier gratis

Según `handbook/company/pricing-features-table.yml` del propio repo de Fleet:

- **Gratis**: MDM multiplataforma, self-hosted, **"Enforce OS settings" = subir perfiles
  `.mobileconfig`** (esto ES el kiosko), DDM, enrolamiento por liga + QR, inventario, políticas,
  labels, scripts, webhooks, dashboards.
- **Premium**: zero-touch ADE, despliegue de apps, lock/wipe remoto, Android device owner,
  Fleets/teams, cifrado de disco, updates de SO forzados.

El kiosko de los iPads cabe completo en el gratis: se supervisa cada iPad con **Apple Configurator**
(USB, **borra el aparato**) enrolándolo a Fleet en el mismo paso, y luego Fleet empuja el perfil
`com.apple.app.lock` + Web Clip + filtro de contenido.

⚠️ `com.apple.app.lock` apunta a un **bundle ID** y un Web Clip **no tiene**: el blanco será Safari
con filtro de contenido a `renopartes.com`, o un envoltorio WKWebView.

## Variables de entorno (se ponen en Coolify, nunca aquí)

| Variable | Nota |
|---|---|
| `MYSQL_ROOT_PASSWORD` | obligatoria |
| `MYSQL_PASSWORD` | obligatoria |
| `MYSQL_DATABASE` / `MYSQL_USER` | por omisión `fleet` |
| `FLEET_SERVER_PRIVATE_KEY` | `openssl rand -base64 32`. **Si se pierde, hay que rehacer el MDM**: cifra los secretos, incluido el push cert de APNs |
| `FLEET_LICENSE_KEY` | vacío = gratis |

## Actualizar

Cambiar el tag de `fleetdm/fleet` en el compose, `git push`, y **Redeploy** en Coolify.
La imagen va **pinneada** a propósito: con `:latest` un redeploy cualquiera podría meter una
migración de base no planeada.

## Después del primer arranque

1. Crear el admin en la consola.
2. `Settings → Organization` → poner la URL base en `https://fleet.renopartes.com` (de ahí sale el
   `ServerURL` de los perfiles de enrolamiento; si está mal, los aparatos no hacen check-in).
3. `Settings → Integrations → MDM` → **Turn on** Apple → bajar CSR → `identity.apple.com` → subir
   el `.pem`.
   ⚠️ **El push cert se renueva cada año.** Calendarizarlo: si vence, la flota entera se queda muda.
