ZIPFILE := google-cloud-functions.zip

.PHONY: upload
upload:
	find . -name "*.py" -print | zip ${ZIPFILE} requirements.txt -@
	gcloud storage cp ${ZIPFILE} gs://observeinc/google-cloud-functions-`semtag getcurrent`.zip

.PHONY: changelog
changelog:
	git-chglog -o CHANGELOG.md --next-tag `semtag final -s minor -o`

.PHONY: release
release: upload
	semtag final -s minor
