# chainer-cfn: Cloudformation Template for ChainerMN on AWS
This template automates to build ChainerMN cluster on AWS. The overview of AWS resources to be created by this template are below:

- VPC and Subnet where cluster places (you can configure existing VPC/Subnet)
- S3 Bucket for sharing ephemeral ssh-key which is used to communicate among MPI processes in the cluster
- Placement group for optimizing network performance
- ChainerMN cluster which consists
  - `1` master EC2 instance
  - `N (>=0)` worker instnaces (via AutoScalingGroup)
  - `chainer` user to run mpi job in each instance
  - `hostfile` to run mpi job in each instance
  - All the instances are launched from [Chainer AMI](https://github.com/chainer/chainer-ami)
- (Option) Amazon Elastic Filesystem (you can configure existing filesystem)
  -  This is mounted on cluster instances automatically to share your code and data.
- Several required SecurityGroups, IAM Role

Please see [template/main.py](template/main.py) for detailed resource definitions.

## The Latest Published Template

- [chainer-cfn-v 0.1.0.template](https://s3-us-west-2.amazonaws.com/chainer-cfn/chainer-cfn-v0.1.0.template)


## Quick Start

Please also refer to our blog: [ChainerMN on AWS with CloudFormation](https://chainer.org/general/2018/06/01/chainermn-on-aws-with-cloudformation.html)

[![launch stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home#/stacks/new?stackName=chainermn-sample&templateURL=https://s3-us-west-2.amazonaws.com/chainer-cfn/chainer-cfn-v0.1.0.template)


## Development Manual
### How to build a template
```
make build
```

### How to test
```
# Configure AWS account properly first.

# this will create a stack via a template you built.
make create-stack TEST_STACK=YOUR_TEST_STACK_NAME KEY_PAIR_NAME=YOUR_KEY_PAIR_NAME

# perform ChainerMN's train_mnist.py
make e2e-test TEST_STACK=YOUR_TEST_STACK_NAME KEY_PAIR_NAME=YOUR_KEY_PAIR_NAME

# cleanup stack
make delete-stack TEST_STACK=YOUR_TEST_STACK_NAME  KEY_PAIR_NAME=YOUR_KEY_PAIR_NAME
```

### How to release
```
# Configure AWS account properly first.

# build template
make build

# perform e2e test
make create-stack TEST_STACK=YOUR_TEST_STACK_NAME KEY_PAIR_NAME=YOUR_KEY_PAIR_NAME
make e2e-test TEST_STACK=YOUR_TEST_STACK_NAME KEY_PAIR_NAME=YOUR_KEY_PAIR_NAME
make delete-stack TEST_STACK=YOUR_TEST_STACK_NAME KEY_PAIR_NAME=YOUR_KEY_PAIR_NAME

# publish to stage
make publish STAGE=(production|staging)
```

## Release Notes
### Version 0.1.0
- Initial release
  - Based on [Chainer AMI `0.1.0`](https://github.com/chainer/chainer-ami)
- Released Template
  - [chainer-cfn-v 0.1.0.template](https://s3-us-west-2.amazonaws.com/chainer-cfn/chainer-cfn-v0.1.0.template)

## License

MIT License (see `LICENSE` file).
