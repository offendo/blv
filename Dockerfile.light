FROM buildpack-deps:bookworm-curl

ARG LEAN_VERSION

ENV ELAN_HOME=/usr/local/elan \
    PATH=/usr/local/elan/bin:$PATH \
    N_WORKERS=1

SHELL ["/bin/bash", "-euxo", "pipefail", "-c"]

# Install
# 1. Lean toolchain
# 2. Redis
# 3. repl
# 4. blv
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y --no-modify-path --default-toolchain leanprover/lean4:${LEAN_VERSION}; \
    chmod -R a+w $ELAN_HOME; \
    elan --version; \
    lean --version; \
    leanc --version; \
    lake --version; \
    apt update -y; \
    apt install -y git lsb-release gcc redis python3 python3-pip; \
    git clone --depth 1 --branch ${LEAN_VERSION} https://github.com/offendo/repl.git; \
    git clone --depth 1 --branch main https://github.com/offendo/blv.git; \
    (cd repl && lake build); \
    (cd blv && pip install --break-system-packages -r requirements.lock);

WORKDIR /blv
