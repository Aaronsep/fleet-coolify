# Imagen de Fleet para Reno: la oficial + el binario parchado (kiosko Android).
#
# El binario lo compila .github/workflows/build-fleet-reno.yml en GitHub Actions y lo
# publica como asset de un Release de este repo. Aquí sólo se baja y se cambia, para que
# el server de Coolify NO tenga que compilar Fleet (yarn + webpack + go) al lado de
# producción.
#
# Todo lo demás (usuario, certs, CMD) queda igual que en la imagen oficial.

ARG FLEET_UPSTREAM_IMAGE=fleetdm/fleet:v4.90.2
FROM ${FLEET_UPSTREAM_IMAGE}

ARG FLEET_BINARY_URL
ARG FLEET_BINARY_SHA256

USER root
RUN set -eux; \
    test -n "$FLEET_BINARY_URL"; \
    test -n "$FLEET_BINARY_SHA256"; \
    wget -q -O /tmp/fleet "$FLEET_BINARY_URL"; \
    echo "$FLEET_BINARY_SHA256  /tmp/fleet" | sha256sum -c -; \
    install -o root -g root -m 0755 /tmp/fleet /usr/bin/fleet; \
    rm -f /tmp/fleet; \
    /usr/bin/fleet version
USER fleet

CMD ["fleet", "serve"]
