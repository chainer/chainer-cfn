VERSION=0.1.0

ifeq ($(STAGE),staging)
	PUBLISH_TO = s3://chainer-cfn-staging
	S3_ACL = 
endif

ifeq ($(STAGE),production)
	PUBLISH_TO = s3://chainer-cfn
	S3_ACL = --grants read=uri=http://acs.amazonaws.com/groups/global/AllUsers
endif

TEST_STACK ?= chainer-cfn-test
KEYPAIR_DIR ?= ~/.ssh
SSH_USER ?= chainer

AWS ?= /usr/local/bin/aws

.PHONY: build pip
pip:
	pip install -r requirements.txt
build: pip
	mkdir -p build
	cd template && \
        python main.py > ../build/template.yaml

.PHONY: validate
validate: build
	$(AWS) cloudformation validate-template --template-body file://./build/template.yaml

.PHONY: publish
publish: validate
	$(AWS) s3 cp build/template.yaml $(PUBLISH_TO)/chainer-cfn-v$(VERSION).template $(S3_ACL)

.PHONY: test
create-stack: validate
	$(AWS) cloudformation create-stack \
		--capabilities CAPABILITY_IAM \
		--stack-name $(TEST_STACK) \
		--template-body file://build/template.yaml \
		--parameters \
				ParameterKey=KeyPairName,ParameterValue=$(KEY_PAIR_NAME) \
				ParameterKey=InstanceType,ParameterValue=g2.2xlarge \
				ParameterKey=WorkerSize,ParameterValue=2 && \
	$(AWS) cloudformation wait stack-create-complete \
		--stack-name $(TEST_STACK) && \
	$(AWS) cloudformation describe-stacks \
		--stack-name $(TEST_STACK) \
		--query 'Stacks[*].StackStatus' \
		--output text && \
	$(AWS) cloudformation describe-stacks \
		--stack-name $(TEST_STACK) \
		--query '(Stacks[*].Outputs[?OutputKey==`ClusterMasterPublicDNS`][])[0].OutputValue' \
		--output text

delete-stack:
	$(AWS) s3 rm --recursive s3://$(TEST_STACK)-assets && \
	$(AWS) cloudformation delete-stack --stack-name $(TEST_STACK) && \
	$(AWS) cloudformation wait stack-delete-complete --stack-name $(TEST_STACK)

.PHONY: stack-master
stack-master:
	@$(AWS) cloudformation describe-stacks \
		--stack-name $(TEST_STACK) \
		--query '(Stacks[*].Outputs[?OutputKey==`ClusterMasterPublicDNS`][])[0].OutputValue' \
		--output text

.PHONY: e2e-test
e2e-test:
	cat e2e/test.sh | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i $(KEYPAIR_DIR)/$(KEY_PAIR_NAME).pem chainer@$$(make stack-master TEST_STACK=$(TEST_STACK))

.PHONY: clean
clean:
	rm -rf build/
