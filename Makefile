ZIPFILE := google-cloud-functions.zip

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

.PHONY: test
test:
	gcloud pubsub topics create cloud-func-test || true # ignore errors
	PARENT=projects/terraflood-345116 \
	TOPIC_ID="projects/terraflood-345116/topics/cloud-func-test" \
	LOCATION_ALLOWLIST=us-west2,us-west1,us-central1 \
	python3 -m unittest discover -p '*.py'	
	# Run this to delete the topic
	# gcloud pubsub topics delete cloud-func-test

.PHONY: test-pubsub-output
test-pubsub-output:
	gcloud pubsub subscriptions create cloud-func-test --topic=cloud-func-test || true
	gcloud --format json pubsub subscriptions pull cloud-func-test
	# Run this to delete the subscription
	# gcloud pubsub subscriptions delete cloud-func-test

.PHONY: fmt
fmt:
	python -m black .
