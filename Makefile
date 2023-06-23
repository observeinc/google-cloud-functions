ZIPFILE := google-cloud-functions.zip
IMAGE_NAME := observe/google-cloud-functions
CONTAINER_NAME := observe-gcp
PROJECT_ID ?= default_project_id
UID := $(shell id -u)
GID := $(shell id -g)
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
	@echo "  build             Build the Docker image."
	@echo "  dev               Run the Docker image."
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

.PHONY: build
build:
	docker build --build-arg UID=$(UID) --build-arg GID=$(GID) -t $(IMAGE_NAME) .

.PHONY: dev
dev: build
	docker run -it --rm --name $(CONTAINER_NAME) -v $(PWD):/src -e PROJECT_ID=$(PROJECT_ID) -u $(UID):$(GID) $(IMAGE_NAME)
