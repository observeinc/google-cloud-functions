ZIPFILE := google-cloud-functions.zip

.PHONY: upload
upload:
	find . -name "*.py" -not -path "./env/*" -print | zip ${ZIPFILE} requirements.txt -@
	gcloud storage cp ${ZIPFILE} gs://observeinc/google-cloud-functions-`semtag getcurrent`.zip
	rm ${ZIPFILE}

.PHONY: changelog
changelog:
	git-chglog -o CHANGELOG.md --next-tag `semtag final -s minor -o`

.PHONY: release
release: upload
	semtag final -s minor

.PHONY: test
test:
	PARENT=projects/terraflood-345116 \
	TOPIC_ID="" \
	LOCATION_ALLOWLIST=us-west2,us-west1,us-central1 \
	python3 -m unittest discover -p '*.py'

.PHONY: fmt
fmt:
	python -m black .
