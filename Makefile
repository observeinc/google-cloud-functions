ZIPFILE := google-cloud-functions.zip
IMAGE_NAME := observe/google-cloud-functions
CONTAINER_NAME := observe-gcp
PROJECT_ID ?= default_project_id
UID := $(shell id -u)
GID := $(shell id -g)
DOCKER_ENV ?= dev
BUCKET_NAME ?= observeinc
PYTHON_FILES ?= . -name "*.py" -not -path "./env/*" -print
SEMTAG_VERSION_SUFFIX ?= `semtag getcurrent`
PRERELEASE_TYPE ?= alpha

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  changelog         Generate a changelog."
	@echo "  release           Generate a new release."
	@echo "  prerelease        Generate a new pre-release."
	@echo "  upload            Upload the zipfile to Google Cloud Storage."
	@echo "  fmt               Format the Python code using Black."
	@echo "  install           Install the required packages."
	@echo "  test              Run the tests."
	@echo "  docker/build      Build the Docker image."
	@echo "  docker/dev        Run the Docker image."
	@echo "  docker/test       Run the tests inside the Docker image."
	@echo "  help              Show this help message."

.PHONY: changelog
changelog:
	git-chglog -o CHANGELOG.md --next-tag `semtag final -s minor -o`

.PHONY: release
release:
	semtag final -s minor
	make upload TARGET=google-cloud-functions-$(SEMTAG_VERSION_SUFFIX)
	make upload TARGET=google-cloud-functions-latest

.PHONY: prerelease
prerelease:
	semtag $(PRERELEASE_TYPE) -s minor
	make upload TARGET=google-cloud-functions-$(SEMTAG_VERSION_SUFFIX)

.PHONY: upload
upload:
	find $(PYTHON_FILES) | zip ${ZIPFILE} requirements.txt -@
	gcloud storage cp --quiet ${ZIPFILE} gs://$(BUCKET_NAME)/$(TARGET).zip
	rm ${ZIPFILE}

.PHONY: fmt
fmt:
	python -m black .

.PHONY: install
install:
	pip install -r requirements.txt -r requirements-dev.txt

.PHONY: test
test: install
	PARENT=testing/test \
	PROJECT_ID=project_placeholder \
	TOPIC_ID=topic_placeholder \
	OUTPUT_BUCKET=gs://bucket_placeholder \
	TASK_QUEUE=queue_placeholder \
	GCP_REGION=gcp_placeholder \
	SERVICE_ACCOUNT_EMAIL=nobody@observeinc.com \
	GCS_TO_PUBSUB_CLOUD_FUNCTION=cloudfunction_placeholder \
	python -m pytest tests/

.PHONY: clean
clean: docker/clean
	find . -name "*.pyc" -type f -delete
	find . -name "*.pyo" -type f -delete
	find . -name "__pycache__" -type d -delete
	find . -name ".pytest_cache" -type d -delete

.PHONY: docker/clean
docker/clean:
	docker rmi -f $(IMAGE_NAME)

.PHONY: docker/build
docker/build:
	@if [ -z $(shell docker images -q $(IMAGE_NAME)) ]; then \
		docker build --build-arg UID=$(UID) --build-arg GID=$(GID) -t $(IMAGE_NAME) .; \
	fi

.PHONY: docker/dev
docker/dev: docker/build
	docker run -it --rm --name $(CONTAINER_NAME) -v $(PWD):/src -e PROJECT_ID=$(PROJECT_ID) -e ENV=$(DOCKER_ENV) -u $(UID):$(GID) $(IMAGE_NAME)

.PHONY: docker/test
docker/test: docker/build
	docker run -it --rm -v $(PWD):/src -e PROJECT=test -e ENV=test -u $(UID):$(GID) $(IMAGE_NAME) make test
