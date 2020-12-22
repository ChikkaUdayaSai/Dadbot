# Extend the official Rasa SDK image
FROM rasa/rasa-sdk:2.0.0

USER 0
RUN groupadd -g 1000 -r debian && \
  useradd -u 1000 -r -g debian debian

# Copy config files and actions folder to working directory
WORKDIR /app
COPY . /app

# By best practices, don't run the code with root user
RUN chgrp -R 1000 /app && chmod -R g=u /app
USER 1000
ENV HOME /app

# Install extra requirements for actions code, if necessary (uncomment next line)
RUN source /opt/venv/bin/activate venv && \
    python3 -m pip install -t /app/.local --upgrade pip && \
    python3 -m pip install -t /app/.local --upgrade --no-cache-dir --use-feature=2020-resolver -r requirements.txt && \
    python3 -m pip install -t /app/.local --upgrade --no-cache-dir --use-feature=2020-resolver -r actions/requirements-actions.txt
ENV PATH "/app/.local/bin:/opt/venv/bin:/bin:/usr/bin:/usr/local/bin"
ENV PYTHONPATH "/app/.local/:/opt/venv/:/usr/local/"

EXPOSE 5005 5055 8000
CMD ["start", "--actions", "actions"]
