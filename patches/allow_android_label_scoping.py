#!/usr/bin/env python3
"""Deja acotar perfiles Android por etiqueta sin licencia Premium.

Sin esto, en Fleet gratis TODO perfil Android cae en TODOS los Android (no hay teams) y subir uno
con labels_include_any / labels_exclude_any responde
"Scoping configuration profiles with labels requires Fleet Premium license".

El candado y el motor viven FUERA de ee/, o sea bajo la licencia MIT del LICENSE de la raíz:
  * el candado: server/service/mdm.go -> parseAndValidateAndroidConfigProfile (subir) y la rama
    "sólo etiquetas" de updateMDMAndroidConfigProfile (PATCH), vía checkLabelsOnlyProfileUpdate;
  * el motor: server/datastore/mysql/android.go -> androidApplicableProfilesQuery ya resuelve
    include-all / include-any / exclude-any, y el reconciliador
    (server/mdm/android/service/profiles.go) no mira la licencia.
En ee/ no hay código de perfiles Android. Los TEAMS sí son ee/ (ee/server/service/teams.go) y NO
se tocan: se acota con etiquetas MANUALES globales (las Android no corren osquery).

Sólo se abren las dos rutas de Android. BatchSetMDMProfiles (gitops / fleetctl apply) y las rutas
de Apple y Windows siguen pidiendo Premium.

Uso: allow_android_label_scoping.py <server/service/mdm.go>
Falla con código 1 si no encuentra qué cambiar (para que el build truene, no para que pase de
largo con un binario sin parchar).
"""
import sys

LICENSE_MSG = "fleet.ConfigProfileLabelScopingPremiumCauseMsg"

# parseAndValidateAndroidConfigProfile: el candado al subir (POST /configuration_profiles).
# `lic` se sigue usando arriba, en el candado de teams, así que no queda variable sin usar.
CREATE_OLD = """	if len(labelsInclude) > 0 || len(labelsExcludeAny) > 0 {
		if lic == nil || !lic.IsPremium() {
			return nil, "", ctxerr.Wrap(ctx, fleet.NewLicenseErrorWithCause(fleet.ConfigProfileLabelScopingPremiumCauseMsg), "checking license for profile label scoping")
		}
	}

	cp := fleet.MDMAndroidConfigProfile{
"""
CREATE_NEW = """	// [Reno] Acotar perfiles Android por etiqueta no exige Premium: el motor
	// (androidApplicableProfilesQuery) ya lo resuelve. El traslape include/exclude se sigue
	// validando más abajo con fleet.LabelOverlap.

	cp := fleet.MDMAndroidConfigProfile{
"""

# updateMDMAndroidConfigProfile: el PATCH que sólo cambia etiquetas. checkLabelsOnlyProfileUpdate
# es compartida con Apple y Windows, así que no se toca: aquí se cambia la llamada por la parte
# que no es de licencia (el traslape).
UPDATE_OLD = """		// no new content -- only labels are being changed.
		if err := svc.checkLabelsOnlyProfileUpdate(ctx, labelsInclude, labelsExcludeAny); err != nil {
			return err
		}
		includeLabels, excludeLabels, err := svc.validateProfileLabelSets(ctx, &teamID, labelsInclude, labelsExcludeAny)
		if err != nil {
			return ctxerr.Wrap(ctx, err, "validating labels")
		}
		cp = &fleet.MDMAndroidConfigProfile{
"""
UPDATE_NEW = """		// no new content -- only labels are being changed.
		// [Reno] Sin el candado de Premium; sólo el traslape include/exclude.
		if overlap := fleet.LabelOverlap(labelsInclude, labelsExcludeAny); overlap != "" {
			return ctxerr.Wrap(ctx, fleet.NewInvalidArgumentError("labels", fmt.Sprintf("label %q cannot appear in both include and exclude lists", overlap)))
		}
		includeLabels, excludeLabels, err := svc.validateProfileLabelSets(ctx, &teamID, labelsInclude, labelsExcludeAny)
		if err != nil {
			return ctxerr.Wrap(ctx, err, "validating labels")
		}
		cp = &fleet.MDMAndroidConfigProfile{
"""


def func_body(src, name):
    start = src.find("\nfunc (svc *Service) %s(" % name)
    if start == -1:
        sys.exit("ERROR: no encontré la función %s" % name)
    end = src.find("\nfunc ", start + 1)
    return src[start:end if end != -1 else len(src)]


path = sys.argv[1]
src = open(path, encoding="utf-8").read()

for old, new in ((CREATE_OLD, CREATE_NEW), (UPDATE_OLD, UPDATE_NEW)):
    if src.count(old) != 1:
        sys.exit("ERROR: esperaba 1 ancla en %s, encontré %d:\n%s" % (path, src.count(old), old))
    src = src.replace(old, new)

# verificación dura: las dos funciones de Android ya no pueden pedir Premium por etiquetas
for name in ("parseAndValidateAndroidConfigProfile", "updateMDMAndroidConfigProfile"):
    body = func_body(src, name)
    if LICENSE_MSG in body or "checkLabelsOnlyProfileUpdate" in body:
        sys.exit("ERROR: %s sigue pidiendo Premium para etiquetas después del parche" % name)

open(path, "w", encoding="utf-8").write(src)
print("Parche aplicado: perfiles Android acotables por etiqueta sin Premium en %s" % path)
