FROM python

ENV PATH=$PATH:/usr/local/bin/google-cloud-sdk/bin/

RUN curl https://sdk.cloud.google.com > install.sh && \
    bash install.sh --disable-prompts --install-dir=/usr/local/bin && \
    gcloud --version && \
    rm -rf install.sh

WORKDIR /src

COPY . /src

RUN pip install -r requirements.txt

# gcloud auth application-default login
# gcloud auth application-default set-quota-project content-eng-colin
