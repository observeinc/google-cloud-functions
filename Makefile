ZIPFILE := google-cloud-functions.zip
IMAGE_NAME=observe/google-cloud-functions
CONTAINER_NAME=observe-gcp
PROJECT_ID?=$(shell echo "default_project_id")
UID=$(shell id -u)
GID=$(shell id -g)


.PHONY: changelog
changelog:
	git-chglog -o CHANGELOG.md --next-tag `semtag final -s minor -o`

.PHONY: release
release:
	semtag final -s minor
	make upload
	make upload-latest

.PHONY: upload
upload:
	find . -name "*.py" -not -path "./env/*" -print | zip ${ZIPFILE} requirements.txt -@
	gcloud storage cp ${ZIPFILE} gs://observeinc/google-cloud-functions-`semtag getcurrent`.zip
	rm ${ZIPFILE}

upload-latest:
	find . -name "*.py" -not -path "./env/*" -print | zip ${ZIPFILE} requirements.txt -@
	gcloud storage cp ${ZIPFILE} gs://observeinc/google-cloud-functions-latest
	rm ${ZIPFILE}

.PHONY: fmt
fmt:
	python -m black .

.PHONY: build
build:
	docker build --build-arg UID=$(UID) --build-arg GID=$(GID) -t $(IMAGE_NAME) .

.PHONY: dev
dev: build
	docker run -it --rm --name $(CONTAINER_NAME) -v $(PWD):/src -e PROJECT_ID=$(PROJECT_ID) -u $(shell id -u):$(shell id -g) $(IMAGE_NAME)

