# Keep the pinned upstream CE runtime and dependencies; rebuild only UI assets.
FROM chatwoot/chatwoot:v4.18.0-ce@sha256:faaa58a911cda8f2ab9d717ddf8ca4332163b07da4c5da10711d896e5d667442 AS ui-deps
WORKDIR /app
RUN node /usr/local/lib/node_modules/npm/bin/npm-cli.js install -g pnpm@10.2.0
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
FROM ui-deps AS ui-build
COPY app/javascript ./app/javascript
COPY app/views/layouts/vueapp.html.erb ./app/views/layouts/vueapp.html.erb
COPY theme ./theme
COPY tailwind.config.js vite.config.ts vite.shared.ts ./
COPY public/mesa ./public/mesa
ARG NODE_OPTIONS="--max-old-space-size=4096"
ENV NODE_OPTIONS=${NODE_OPTIONS}
RUN rm -rf public/vite && SECRET_KEY_BASE=precompile_placeholder RAILS_LOG_TO_STDOUT=enabled bundle exec rake assets:precompile

FROM chatwoot/chatwoot:v4.18.0-ce@sha256:faaa58a911cda8f2ab9d717ddf8ca4332163b07da4c5da10711d896e5d667442
ARG MESA_REVISION
LABEL org.opencontainers.image.source="https://github.com/mesainc/chatwoot" org.opencontainers.image.revision="$MESA_REVISION"
COPY --from=ui-build /app/public/vite /app/public/vite
COPY --from=ui-build /app/public/assets /app/public/assets
COPY public/mesa /app/public/mesa
COPY app/views/layouts/vueapp.html.erb /app/app/views/layouts/vueapp.html.erb

RUN test -n "$MESA_REVISION" && printf '%s\n' "$MESA_REVISION" > /app/.git_sha
