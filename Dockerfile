FROM buildpack-deps:bookworm-curl

ARG LEAN_VERSION

ENV ELAN_HOME=/usr/local/elan \
    PATH=/usr/local/elan/bin:$PATH

SHELL ["/bin/bash", "-euxo", "pipefail", "-c"]

# Install
# 1. Lean toolchain
# 2. Redis
# 3. repl
# 4. pyleanrepl
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y --no-modify-path --default-toolchain leanprover/lean4:${LEAN_VERSION}; \
    chmod -R a+w $ELAN_HOME; \
    elan --version; \
    lean --version; \
    leanc --version; \
    lake --version;

RUN apt update -y; \
    apt install -y git lsb-release gcc redis python3 python3-pip; \
    git clone --depth 1 --branch v4.20.0-rc5 https://github.com/offendo/repl.git; \
    git clone --depth 1 --branch main https://github.com/offendo/pyleanrepl.git; \
    (cd repl && lake update && lake exe cache get && lake build);

RUN (cd pyleanrepl && pip install --break-system-packages -r requirements.lock);

WORKDIR /pyleanrepl
ENV N_WORKERS=32
CMD ["bash", "start_workers.sh"]
