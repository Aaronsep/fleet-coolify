# Fleet en Coolify (Reno Partes)

MDM autohospedado para la **flota de iPads** y, desde el 2026-09-02, también para los
**Android en kiosko**. Es [Fleet](https://github.com/fleetdm/fleet), MIT en el core, con **el
binario parchado** (ver *Fork: las llaves de kiosko Android* más abajo).

> Corrección a lo que decía antes este README: enrolar Android *company-owned / fully managed*
> (device owner) **NO es Premium** — la liga de enrolamiento lleva `?fully_managed=true` y ya.
> Lo que sí es Premium es **desplegar apps** (`/software/app_store_apps` responde 402), por eso
> el APK del BackOffice se mete por `adb install`.

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

## Fork: las llaves de kiosko Android

Fleet **rechaza al subir** un perfil Android que traiga `kioskCustomLauncherEnabled`,
`kioskCustomization` o `persistentPreferredActivities`: están en `AndroidForbiddenJSONKeys`
(`server/fleet/android.go`) con el mensaje *"Currently, only personal hosts are supported."*

🔑 **No es muro de pago ni límite de Google, y no depende de la versión** (la lista es igual en
`main`): el *field mask* con el que Fleet le parcha la política a Google
(`server/mdm/android/service/androidmgmt/google_client.go`) **ya incluye esas tres llaves**, y el
reconciliador manda el JSON crudo del perfil sin volver a validarlo
(`server/mdm/android/service/profiles.go`). El freno está **sólo en el validador de subida**.

Por eso aquí el binario va parchado:

- `patches/allow_android_kiosk_keys.py` quita esas tres entradas del mapa. **Truena si no las
  encuentra** — así un cambio de upstream rompe el build en vez de publicar un binario sin parchar.
- `.github/workflows/build-fleet-reno.yml` compila en **GitHub Actions** (no en el server de Reno:
  ese server corre producción y un build de Fleet = yarn + webpack + go) con las mismas banderas
  del `.goreleaser.yml` de upstream — **estático**, porque la imagen oficial es alpine/musl y un
  binario ligado a glibc no corre ahí — y sube el binario como asset de un Release de este repo.
- `image/Dockerfile` lo pone encima de la imagen oficial, verificando **SHA256**.

**No se libera `applications`** a propósito: Fleet parcha las apps por separado
(`EnterprisesPoliciesModifyPolicyApplications`) y su patch normal las excluye
(`PoliciesPatchOpts{ExcludeApps: true}`), así que una lista de apps en un perfil **no llegaría a
Google** y encima pelearía con la app-agente de Fleet.

### Subir de versión

1. Editar `FLEET_TAG` / `RELEASE_TAG` al correr el workflow (`workflow_dispatch`).
2. Copiar el SHA256 que imprime el resumen del run.
3. Actualizar `FLEET_BINARY_URL`, `FLEET_BINARY_SHA256` y `FLEET_UPSTREAM_IMAGE` en el compose.
4. `git push` y **Redeploy** en Coolify.

⚠️ El parche hay que rehacerlo (o revalidarlo) en **cada** actualización de Fleet. Si upstream
libera esas llaves por su cuenta, el script truena y ahí se quita el parche.

## Variables de entorno (se ponen en Coolify, nunca aquí)

| Variable | Nota |
|---|---|
| `MYSQL_ROOT_PASSWORD` | obligatoria |
| `MYSQL_PASSWORD` | obligatoria |
| `MYSQL_DATABASE` / `MYSQL_USER` | por omisión `fleet` |
| `FLEET_SERVER_PRIVATE_KEY` | `openssl rand -base64 32`. **Si se pierde, hay que rehacer el MDM**: cifra los secretos, incluido el push cert de APNs |
| `FLEET_LICENSE_KEY` | vacío = gratis |

## Actualizar

Ver *Fork: las llaves de kiosko Android → Subir de versión*. La imagen base va **pinneada** a
propósito: con `:latest` un redeploy cualquiera podría meter una migración de base no planeada.

## Después del primer arranque

1. Crear el admin en la consola.
2. `Settings → Organization` → poner la URL base en `https://fleet.renopartes.com` (de ahí sale el
   `ServerURL` de los perfiles de enrolamiento; si está mal, los aparatos no hacen check-in).
3. `Settings → Integrations → MDM` → **Turn on** Apple → bajar CSR → `identity.apple.com` → subir
   el `.pem`.
   ⚠️ **El push cert se renueva cada año.** Calendarizarlo: si vence, la flota entera se queda muda.

## Trampas que costaron el despliegue

1. **Coolify inyecta `restart: unless-stopped` a TODOS los servicios del compose.** El
   `fleet-init` de upstream es de un solo uso (`chown` y salir) y lo esperan con
   `depends_on: service_completed_successfully`. En Coolify ese contenedor sale con 0, Docker lo
   revive, y la condición "completed" **nunca se estabiliza**: el deploy se cuelga esperándola y
   la app queda en `restarting:unknown`. Aquí el init hace el `chown`, se queda vivo, y avisa que
   terminó por **healthcheck** (`test -f /tmp/done`), con `condition: service_healthy`.
2. **Upstream monta `./certs/fleet.{crt,key}` siempre**, incluso con `FLEET_SERVER_TLS=false`.
   Si esos archivos no existen en el repo el contenedor no arranca. Aquí no se montan.
