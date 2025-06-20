# syntax=docker/dockerfile:1.4
FROM python:3.11-slim AS builder

# 1) Install build tools, JDK & native deps for jnius
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      python3-dev \
      default-jdk \
      swig \
      libffi-dev \
      pkg-config \
 && rm -rf /var/lib/apt/lists/*

# 2) Tell jnius’s setup exactly where the JDK is
ENV JAVA_HOME=/usr/lib/jvm/default-java \
    JDK_HOME=/usr/lib/jvm/default-java \
    PATH="$JAVA_HOME/bin:$PATH"

WORKDIR /app
COPY requirements.txt .

# 3) Cache wheels, install Cython & then all your deps (including jnius)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir Cython \
 && pip install \
      --use-deprecated=legacy-resolver \
      --no-cache-dir \
      -r requirements.txt

################
# Runtime stage #
################
FROM python:3.11-slim AS runner

# (4) Only JRE at runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre \
 && rm -rf /var/lib/apt/lists/*

# (5) Set Java env so your app can still call into jnius
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 \
    JDK_HOME=/usr/lib/jvm/java-11-openjdk-amd64

WORKDIR /app

# (6) Copy in the already-built site-packages & scripts
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin               /usr/local/bin

# (7) Your app code
COPY ./app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
