# Use a builder image for installing google cloud sdk
FROM python:3.8-slim-buster

# Accept the user ID and group ID as build arguments
ARG UID=1000
ARG GID=1000

WORKDIR /install

# Environment variable to find the google-cloud-sdk
ENV PATH=$PATH:/usr/local/bin/google-cloud-sdk/bin/

# Install Google Cloud SDK
RUN apt-get update -y && apt-get install -y curl make && \
    curl https://sdk.cloud.google.com > install.sh && \
    bash install.sh --disable-prompts --install-dir=/usr/local/bin && \
    gcloud --version && \
    rm -rf install.sh

# Create a group and user with the provided IDs, and create a home directory for the user
RUN groupadd -r gcpuser -g ${GID} && \
    useradd -r -g gcpuser -u ${UID} -m -d /home/gcpuser -s /bin/bash gcpuser && \
    chown -R gcpuser:gcpuser /home/gcpuser

RUN mkdir -p /home/gcpuser/.config && chmod 777 /home/gcpuser/.config

WORKDIR /src

# Copy the local src directory to the Docker image
COPY . /src

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Change the ownership of the src directory to our user and group
RUN chown -R gcpuser:gcpuser /src

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Change to our non-root user and set the home directory
USER gcpuser
ENV HOME=/home/gcpuser

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
