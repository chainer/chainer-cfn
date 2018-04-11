import textwrap
import troposphere
from troposphere import *
from troposphere.autoscaling import *
from troposphere.ec2 import *
from troposphere.iam import *
from troposphere.s3 import *
from troposphere.policies import *
from troposphere.efs import *

import awacs
from awacs.aws import Statement, Allow, Action, Principal

from utils import *


def main():
    t = Template()

    #
    # Metadata
    #
    t.add_metadata(troposphere.cloudformation.Metadata({
        #
        # Interface
        #
        'AWS::CloudFormation::Interface': {
            'ParameterGroups': [
                {
                    'Label': {
                        'default': 'VPC Configuration'
                    },
                    'Parameters': ['VpcId', 'NewVpcCIDR']
                },
                {
                    'Label': {
                        'default': 'Subnet Configuration'
                    },
                    'Parameters': ['SubnetId', 'NewSubnetAZ', 'NewSubnetCIDR', 'NewSubnetRouteTableId']
                },
                {
                    'Label': {
                        'default': 'Cluster Configuration (Cluster = 1 Master + N(>=0) Workers)'
                    },
                    'Parameters': ['InstanceType', 'KeyPairName', 'SSHLocation', 'RootVolumeSize', 'WorkerSize']
                },
                {
                    'Label': {
                        'default': 'Elastic File System(EFS) Configuration'
                    },
                    'Parameters': ['UseEFS', 'EFSFileSystemId', 'ExistingEFSMountTargetSecurityGroupId',
                                   'NewEFSPerformanceMode', 'EFSMountPoint']
                }
            ],
            'ParameterLabels': {
                'VpcId': {
                    'default': 'In which VPC do you want to create cluster?'
                },
                'NewVpcCIDR': {
                    'default': 'new VPC CIDR:'
                },
                'SubnetId': {
                    'default': 'In which Subnet do you want to create cluster?'
                },
                'NewSubnetAZ': {
                    'default': 'Availability Zone for New Subnet:'
                },
                'NewSubnetCIDR': {
                    'default': 'New Subnet CIDR:'
                },
                'NewSubnetRouteTableId': {
                    'default': 'Route table Id for new Subnet:'
                },
                'InstanceType': {
                    'default': 'Instance Type:'
                },
                'KeyPairName': {
                    'default': 'Key Pair:'
                },
                'SSHLocation': {
                  'default': 'SSH Location:'
                },
                'RootVolumeSize': {
                    'default': 'Root Volume Size:'
                },
                'WorkerSize': {
                    'default': 'Worker Size:'
                },
                'UseEFS': {
                    'default': 'Use EFS?'
                },
                'EFSFileSystemId': {
                    'default': 'Which filesystem you want to mount?'
                },
                'ExistingEFSMountTargetSecurityGroupId': {
                    'default': 'SecurityGroup Id attached to existing EFS:'
                },
                'NewEFSPerformanceMode': {
                    'default': 'Performance mode of new EFS:'
                },
                'EFSMountPoint': {
                    'default': 'Mount point of new EFS:'
                }
            }
        }
    }))
    trackingTags = Tags(
        ChainerClusterName=StackName
    )

    #
    # Parameters
    #
    VpcId = t.add_parameter(Parameter(
        "VpcId",
        Description="Id of existing VPC. Leave blank to create a new VPC (including an internet gateway).",
        Default="",
        Type="String",
    ))
    IsVpcIdEmpty = empty(Ref(VpcId))
    t.add_condition("IsVpcIdEmpty", IsVpcIdEmpty)

    NewVpcCIDR = t.add_parameter(Parameter(
        "NewVpcCIDR",
        Description="IP Address range for new VPC.",
        Default="10.0.0.0/16",
        ConstraintDescription="must be a valid IP CIDR range of the form x.x.x.x/x.",
        AllowedPattern="(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})/(\\d{1,2})",
        MaxLength=18,
        Type="String"
    ))

    InstanceTenancy = t.add_parameter(Parameter(
        "InstanceTenancy",
        Description="Instance tenancy for cluster nodes.",
        Default="default",
        AllowedValues=['default', 'dedicated'],
        Type="String"
    ))

    SubnetId = t.add_parameter(Parameter(
        "SubnetId",
        Description="Id of existing Subnet. Leave blank to create a new subnet.",
        Default="",
        Type="String"
    ))

    IsSubnetIdEmpty = empty(Ref(SubnetId))
    t.add_condition("IsSubnetIdEmpty", IsSubnetIdEmpty)

    NewSubnetAZ = t.add_parameter(Parameter(
        "NewSubnetAZ",
        Description="Availability Zone for new subnet, it should be one supporting the instance type in Cluster Configuration Section.  If it's empty, the template just automatically select the first listed availability zone.  Please remember the auto-selected availability zone might not support your instance type.",
        Default="",
        Type="String"
    ))
    IsSubnetAZEmpty = empty(Ref(NewSubnetAZ))
    t.add_condition("IsSubnetAZEmpty", IsSubnetAZEmpty)

    NewSubnetCIDR = t.add_parameter(Parameter(
        "NewSubnetCIDR",
        Description="IP Address range for new subnet.  It is used only when SubnetId is not set.",
        Default="10.0.0.0/16",
        ConstraintDescription="must be a valid IP CIDR range of the form x.x.x.x/x.",
        AllowedPattern="(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})/(\\d{1,2})",
        MaxLength=18,
        Type="String"
    ))

    NewSubnetRouteTableId = t.add_parameter(Parameter(
        "NewSubnetRouteTableId",
        Description="Route table Id to which attached to new subnet.  Please specify this unless VpcId is empty.  If NewSubnetRouteTableId is specified, it's your responsibility to add an appropriate route to an internet gateway or a NAT gateway to the route table.",
        Default="",
        Type="String"
    ))

    InstanceType = t.add_parameter(Parameter(
        "InstanceType",
        Description="Instance type of each node in the cluster. GPU instnaces are highly recommended.",
        Default="p3.16xlarge",
        AllowedValues=[
            "p3.2xlarge",
            "p3.8xlarge",
            "p3.16xlarge",
            "p2.xlarge",
            "p2.8xlarge",
            "p2.16xlarge",
            "g2.2xlarge",
            "g2.8xlarge",
            "g3.4xlarge",
            "g3.8xlarge",
            "g3.16xlarge"
        ],
        Type="String"
    ))

    KeyPairName = t.add_parameter(Parameter(
        "KeyPairName",
        Description="Name of SSH key pair to login to cluster nodes.",
        Type="AWS::EC2::KeyPair::KeyName"
    ))

    SSHLocation = t.add_parameter(Parameter(
        "SSHLocation",
        Description=" The IP address range that can be used to SSH to the EC2 instances",
        Default="0.0.0.0/0",
        ConstraintDescription="must be a valid IP CIDR range of the form x.x.x.x/x.",
        AllowedPattern="(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})/(\\d{1,2})",
        MinLength="9",
        MaxLength="18",
        Type="String"
    ))

    RootVolumeSize = t.add_parameter(Parameter(
        "RootVolumeSize",
        Description="Size(GiB) of root volume for each cluster node.",
        MinValue=1,
        Default=50,
        Type="Number"
    ))

    WorkerSize = t.add_parameter(Parameter(
        "WorkerSize",
        Description="The number of Worker nodes in the cluster. It must be larger than or equal to 0. Put 0 if you wanted a single node cluster.",
        Default=3,
        MinValue=0,
        Type="Number"
    ))

    UseEFS = t.add_parameter(Parameter(
        "UseEFS",
        Description="Switch for using EFS or not.  If this true, The template will auto-mount EFS to the cluster",
        Type="String",
        Default="True",
        AllowedValues=["True", "False"]
    ))
    EFSEnabled = Equals("True", Ref(UseEFS))
    t.add_condition("EFSEnabled", EFSEnabled)

    EFSFileSystemId = t.add_parameter(Parameter(
        "EFSFileSystemId",
        Description="Id of existing EFS filesystem.  Leave blank to create new EFS filesystem.  When specified, the filesystem must have a MountTarget in the availability zone which the cluster is provisioned in.",
        Default="",
        Type="String"
    ))
    IsEFSFileSystemIdEmpty = empty(Ref(EFSFileSystemId))
    t.add_condition("IsEFSFileSystemIdEmpty", IsEFSFileSystemIdEmpty)

    ShouldCreateEFS = And(Condition("EFSEnabled"), Condition("IsEFSFileSystemIdEmpty"))
    t.add_condition('ShouldCreateEFS', ShouldCreateEFS)

    EFSMountPoint = t.add_parameter(Parameter(
        "EFSMountPoint",
        Description="The Linux mount point for EFS. It is relative path from root directory(/).",
        Type="String",
        Default="efs",
        MinLength=1
    ))

    ExistingEFSMountTargetSecurityGroupId = t.add_parameter(Parameter(
        "ExistingEFSMountTargetSecurityGroupId",
        Description="Id of existing SecurityGroup attached to MountTarget in the target availability zone of the EFS filesystem.  You must specify this Id when you specified existing EFS filesystem.  The stack will add an inbound rule so that the cluster can access to it.",
        Default="",
        Type="String"
    ))

    NewEFSPerformanceMode = t.add_parameter(Parameter(
        "NewEFSPerformanceMode",
        Description='The performance mode of EFS file system. It is used only when you don\'t specify existing EFS filesystem',
        Type="String",
        AllowedValues=['generalPurpose', 'maxIO'],
        Default='generalPurpose'
    ))

    #
    # Mapping
    #
    t.add_mapping('RegionMap', {
        # chainer-ami-0.1.0
        "ap-northeast-1": {"AMI": "ami-ca08f0b5"},
        "ap-northeast-2": {"AMI": "ami-d2bb10bc"},
        "ap-south-1": {"AMI": "ami-5daf8032"},
        "ap-southeast-1": {"AMI": "ami-98b689e4"},
        "ap-southeast-2": {"AMI": "ami-df9042bd"},
        "ca-central-1": {"AMI": "ami-37e16253"},
        "eu-central-1": {"AMI": "ami-24685dcf"},
        "eu-west-1": {"AMI": "ami-c3b48fba"},
        "eu-west-2": {"AMI": "ami-370ce050"},
        "eu-west-3": {"AMI": "ami-c95beab4"},
        "sa-east-1": {"AMI": "ami-a1fea0cd"},
        "us-east-1": {"AMI": "ami-ea7f1095"},
        "us-east-2": {"AMI": "ami-dd7946b8"},
        "us-west-1": {"AMI": "ami-2dbba04d"},
        "us-west-2": {"AMI": "ami-ea403b92"}
    })

    t.add_mapping('EBSOptimizationMap', {
        "p3.2xlarge": {"EBSOptimized": True},
        "p3.8xlarge": {"EBSOptimized": True},
        "p3.16xlarge": {"EBSOptimized": True},
        "p2.xlarge": {"EBSOptimized": True},
        "p2.8xlarge": {"EBSOptimized": True},
        "p2.16xlarge": {"EBSOptimized": True},
        "g2.2xlarge": {"EBSOptimized": True},
        "g2.8xlarge": {"EBSOptimized": False},
        "g3.4xlarge": {"EBSOptimized": True},
        "g3.8xlarge": {"EBSOptimized": True},
        "g3.16xlarge": {"EBSOptimized": True}
    })

    #
    # VPC and subnet
    #
    ManagedVpc = t.add_resource(VPC(
        "ManagedVpc",
        Condition="IsVpcIdEmpty",
        CidrBlock=Ref(NewVpcCIDR),
        EnableDnsSupport=True,
        EnableDnsHostnames=True,
        InstanceTenancy=Ref(InstanceTenancy),
        Tags=trackingTags
    ))

    targetVpc = If(
        'IsVpcIdEmpty',
        Ref(ManagedVpc),
        Ref(VpcId),
    )

    ManagedInternetGateway = t.add_resource(InternetGateway(
        "ManagedInternetGateway",
        Condition="IsVpcIdEmpty",
        Tags=trackingTags
    ))

    ManagedInternetGatewayAttachment = t.add_resource(VPCGatewayAttachment(
        "ManagedInternetGatewayAttachment",
        Condition="IsVpcIdEmpty",
        InternetGatewayId=Ref(ManagedInternetGateway),
        VpcId=Ref(ManagedVpc)
    ))

    ManagedVpcMainRouteTable = t.add_resource(RouteTable(
        "ManagedVpcMainRouteTable",
        Condition="IsVpcIdEmpty",
        VpcId=Ref(ManagedVpc),
        Tags=trackingTags
    ))

    ManagedDefaultIGWRoute = t.add_resource(Route(
        "ManagedDefaultIGWRoute",
        Condition="IsVpcIdEmpty",
        RouteTableId=Ref(ManagedVpcMainRouteTable),
        DestinationCidrBlock="0.0.0.0/0",
        GatewayId=Ref(ManagedInternetGateway)
    ))

    ManagedSubnet = t.add_resource(Subnet(
        "ManagedSubnet",
        Condition="IsSubnetIdEmpty",
        CidrBlock=Ref(NewSubnetCIDR),
        AvailabilityZone=If('IsSubnetAZEmpty', Select(0, GetAZs(Region)), Ref(NewSubnetAZ)),
        MapPublicIpOnLaunch=True,
        VpcId=targetVpc,
        Tags=trackingTags
    ))

    targetSubnet = If(
        'IsSubnetIdEmpty',
        Ref(ManagedSubnet),
        Ref(SubnetId)
    )

    targetRouteTable = If(
        'IsVpcIdEmpty',
        Ref(ManagedVpcMainRouteTable),
        Ref(NewSubnetRouteTableId)
    )

    ManagedSubnetRouteTableAssociation = t.add_resource(SubnetRouteTableAssociation(
        "ManagedSubnetRouteTableAssociation",
        Condition="IsSubnetIdEmpty",
        RouteTableId=targetRouteTable,
        SubnetId=Ref(ManagedSubnet)
    ))

    #
    # S3 Bucket to store cluster ssh keys or share user codes.
    #
    AssetBucket = t.add_resource(Bucket(
        "AssetBucket",
        BucketName=Join('-', [StackName, 'assets']),
        Tags=trackingTags
    ))

    #
    # IAM Role
    #
    ClusterWorkerRole = t.add_resource(Role(
        "ClusterWorkerRole",
        AssumeRolePolicyDocument=awacs.aws.Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Principal=Principal("Service", "ec2.amazonaws.com"),
                    Action=[Action("sts", "AssumeRole")]
                )
            ]
        ),
        Policies=[troposphere.iam.Policy(
            PolicyName='ChainerClusterWorkerPolicy',
            PolicyDocument=awacs.aws.Policy(
                Statement=[
                    Statement(
                        Sid="ListInstances",
                        Effect=Allow,
                        Action=[
                            Action("ec2", "Describe*")
                        ],
                        Resource=['*']
                    ),
                    Statement(
                        Sid="CloudWatchPutMetricData",
                        Effect=Allow,
                        Action=[
                            Action('cloudwatch', 'PutMetricData')
                        ],
                        Resource=['*']
                    ),
                    Statement(
                        Sid="AllowBucketOps",
                        Effect=Allow,
                        Action=[
                            Action("s3", "ListBucket"),
                            Action("s3", "ListBucketMultipartUploads"),
                        ],
                        Resource=[
                            GetAtt(AssetBucket, "Arn")
                        ]
                    ),
                    Statement(
                        Sid="AllowReadObjects",
                        Effect=Allow,
                        Action=[
                            Action("s3", "GetObject")
                        ],
                        Resource=[
                            Join('/', [GetAtt(AssetBucket, "Arn"), '*'])
                        ]
                    )
                ]
            )
        )]
    ))

    ClusterMasterRole = t.add_resource(Role(
        "ClusterMasterRole",
        AssumeRolePolicyDocument=awacs.aws.Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Principal=Principal("Service", "ec2.amazonaws.com"),
                    Action=[Action("sts", "AssumeRole")]
                )
            ]
        ),
        Policies=[troposphere.iam.Policy(
            PolicyName='ChainerClusterMasterPolicy',
            PolicyDocument=awacs.aws.Policy(
                Statement=[
                    Statement(
                        Sid="ListInstances",
                        Effect=Allow,
                        Action=[
                            Action("ec2", "Describe*")
                        ],
                        Resource=['*']
                    ),
                    Statement(
                        Sid="CloudWatchPutMetricData",
                        Effect=Allow,
                        Action=[
                            Action('cloudwatch', 'PutMetricData')
                        ],
                        Resource=['*']
                    ),
                    Statement(
                        Sid="AllowBucketOps",
                        Effect=Allow,
                        Action=[
                            Action("s3", "ListBucket"),
                            Action("s3", "ListBucketMultipartUploads"),
                        ],
                        Resource=[
                            GetAtt(AssetBucket, "Arn")
                        ]
                    ),
                    Statement(
                        Sid="AllowWriteObjects",
                        Effect=Allow,
                        Action=[
                            Action("s3", "AbortMultipartUpload"),
                            Action("s3", "ListMultipartUploadParts"),
                            Action("s3", "PutObject")
                        ],
                        Resource=[
                            Join('/', [GetAtt(AssetBucket, "Arn"), '*'])
                        ]
                    )
                ]
            )
        )]
    ))

    #
    # SecurityGroups
    #
    AllowSSHFromExternalSG = t.add_resource(SecurityGroup(
        "AllowSSHFromExternalSG",
        VpcId=targetVpc,
        GroupDescription="allow ssh from anywhere",
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol="tcp",
                FromPort=22,
                ToPort=22,
                CidrIp=Ref(SSHLocation)
            )
        ],
        Tags=trackingTags
    ))

    ClusterMemberMarkerSg = t.add_resource(SecurityGroup(
        "ClusterMemberMarkerSg",
        VpcId=targetVpc,
        GroupDescription="marker security group for cluster member",
        Tags=trackingTags
    ))

    AllowAllAmongClusterMember = t.add_resource(SecurityGroup(
        "AllowAllAmongClusterMember",
        VpcId=targetVpc,
        DependsOn=[ClusterMemberMarkerSg],
        GroupDescription="allow all ports inside of cluster",
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol="tcp",
                FromPort=0,
                ToPort=65535,
                SourceSecurityGroupId=Ref(ClusterMemberMarkerSg)
            )
        ],
        Tags=trackingTags
    ))

    EFSMountTargetSecurityGroup = t.add_resource(SecurityGroup(
        "EFSMountTargetSecurityGroup",
        Condition="ShouldCreateEFS",
        GroupDescription="Security Group for EFS Mount Target",
        VpcId=targetVpc
    ))

    EFSFileSystemSecurityGroupIngress = t.add_resource(SecurityGroupIngress(
        "EFSFileSystemSecurityGroupIngress",
        Condition="EFSEnabled",
        IpProtocol="tcp",
        FromPort=2049,
        ToPort=2049,
        SourceSecurityGroupId=Ref(ClusterMemberMarkerSg),
        GroupId=If(
            "IsEFSFileSystemIdEmpty",
            Ref(EFSMountTargetSecurityGroup),
            Ref(ExistingEFSMountTargetSecurityGroupId)
        )
    ))


    #
    # EFS
    #
    EFSFileSystem = t.add_resource(FileSystem(
        "EFSFileSystem",
        Condition="ShouldCreateEFS",
        PerformanceMode=Ref(NewEFSPerformanceMode),
    ))
    targetFileSystem=If(
        "EFSEnabled",
        If("ShouldCreateEFS",
            Ref(EFSFileSystem),
            Ref(EFSFileSystemId)
        ),
        "fs-00adummy"
    )
    EFSMountTarget = t.add_resource(MountTarget(
        "EFSMountTarget",
        Condition="ShouldCreateEFS",
        FileSystemId=Ref(EFSFileSystem),
        SubnetId=targetSubnet,
        SecurityGroups=[Ref(EFSMountTargetSecurityGroup)]
    ))

    NewEFSHandle = t.add_resource(cloudformation.WaitConditionHandle(
        "NewEFSHandle",
        Condition="ShouldCreateEFS",
        DependsOn=["EFSMountTarget"]
    ))

    NoNewEFSHandle = t.add_resource(cloudformation.WaitConditionHandle(
        "NoNewEFSHandle"
    ))

    EFSReadyWaitCondition = t.add_resource(cloudformation.WaitCondition(
        "EFSReadyWaitCondition",
        Handle= If("ShouldCreateEFS", Ref(NewEFSHandle), Ref(NoNewEFSHandle)),
        Timeout=1,
        Count=0
    ))

    #
    # Cluster Instances
    #
    # ---
    #
    # Placement Group
    #
    ClusterPlacementGroup = t.add_resource(PlacementGroup(
        "ClusterPlacementGroup",
        Strategy='cluster'
    ))

    #
    # Init Configs
    #
    createChainerUserInitConfig = cloudformation.InitConfig(
        files={
            '/root/create-chainer-user.sh': {
                'content': Join('', [
                    '#! /bin/bash\n',
                    'useradd -m chainer -s /bin/bash\n',
                    'cp ~ubuntu/.bashrc ~chainer/.bashrc\n',
                    'chown chainer:chainer /home/chainer/.bashrc\n'
                ]),
                'mode': '000755',
                'owner': 'root',
                'group': 'root'
            }
        },
        commands={
            'create-chainer-user': {
                'command': '/root/create-chainer-user.sh'
            }
        }
    )
    sshClientConfigInitConfig = cloudformation.InitConfig(
        files={
            '/home/chainer/.ssh/environment': {
                'content': Join('', [
                    'PATH=/home/chainer/bin:/home/chainer/.local/bin:/usr/local/cuda/bin:/usr/local/bin:/opt/aws/bin:/home/ubuntu/src/cntk/bin:/usr/local/mpi/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin\n',
                    'LD_LIBRARY_PATH=/home/ubuntu/src/cntk/bindings/python/cntk/libs:/usr/local/cuda/lib64:/usr/local/lib:/usr/lib:/usr/local/cuda/extras/CUPTI/lib64:/usr/local/mpi/lib\n'
                ]),
                'mode': '000644',
                'owner': 'chainer',
                'group': 'chainer'
            },
            '/home/chainer/.ssh/config': {
                'content': Join('', [
                    'StrictHostKeyChecking no\n',
                    'UserKnownHostsFile=/dev/null\n'
                ]),
                'mode': '000644',
                'owner': 'chainer',
                'group': 'chainer'
            }
        }
    )
    provisionClusterKeyInitConfig = cloudformation.InitConfig(
        files={
            '/root/provision-cluster-key.sh': {
                'content': Join('', [
                    '#! /bin/bash\n',
                    'SSH_DIR=~chainer/.ssh\n',
                    'mkdir -p $SSH_DIR\n',
                    'ssh-keygen -q -N "" -f $SSH_DIR/id_rsa\n',
                    'cp $SSH_DIR/id_rsa.pub $SSH_DIR/authorized_keys\n',
                    'chmod 600 $SSH_DIR/id_rsa $SSH_DIR/authorized_keys\n',
                    'chown chainer:chainer $SSH_DIR/*\n',
                    'chmod 755 $SSH_DIR\n',
                    'chown chainer:chainer $SSH_DIR\n',
                    'region=$(curl -sL http://169.254.169.254/latest/meta-data/placement/availability-zone | sed -e \'s/.$//\')\n',
                    'CLUSTER_KEY_BUCKET_NAME=', Ref(AssetBucket), '\n',
                    'aws s3 --region $region cp $SSH_DIR/id_rsa s3://$CLUSTER_KEY_BUCKET_NAME/.ssh/id_rsa\n',
                    'aws s3 --region $region cp $SSH_DIR/id_rsa.pub s3://$CLUSTER_KEY_BUCKET_NAME/.ssh/id_rsa.pub/\n',
                    'aws s3 --region $region cp $SSH_DIR/authorized_keys s3://$CLUSTER_KEY_BUCKET_NAME/.ssh/authorized_keys\n',
                    'cat ~ubuntu/.ssh/authorized_keys >> $SSH_DIR/authorized_keys\n'
                ]),
                'mode': '0755',
                'owner': 'root',
                'group': 'root'
            }
        },
        commands={
            'provision-cluster-key': {
                'command': '/root/provision-cluster-key.sh'
            }
        }
    )

    hostfileUpdaterInitConfig = cloudformation.InitConfig(
        files={
            '/root/hostfile-updater.sh':{
                'content': Join('', [
                    '#! /bin/bash\n',
                    'region=$(curl -sL http://169.254.169.254/latest/meta-data/placement/availability-zone | sed -e \'s/.$//\')\n',
                    'aws ec2 describe-instances',
                    '  --region=$region',
                    '  --filters "Name=tag:ChainerClusterName,Values=', StackName, '"',
                    '  --query=\'Reservations[*][].Instances[?PrivateDnsName!=``][].PrivateDnsName\'',
                    '  --output text | sed -e \'s/\\t/\\n/g\' > /tmp/hostfile.generated\n',
                    'chown chainer:chainer /tmp/hostfile.generated\n',
                    'chmod 644 /tmp/hostfile.generated\n',
                    'mv /tmp/hostfile.generated /usr/local/mpi/etc/openmpi-default-hostfile\n'
                ]),
                'mode': '0755',
                'owner': 'root',
                'group': 'root'
            },
            '/etc/cron.d/hostfile-updater': {
                'content': Join('', [
                    'SHELL=/bin/bash\n',
                    'PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin\n',
                    'MAILTO=""\n',
                    'HOME=/\n',
                    '*/1 * * * * root /root/hostfile-updater.sh\n',
                ]),
                'mode': '000644',
                'owner': 'root',
                'group': 'root'
            }
        },
        services={
            'sysvinit': cloudformation.InitServices({
                "cron": cloudformation.InitService(
                    enabled=True,
                    ensureRunning=True,
                    files=[
                        '/etc/cron.d/hostfile-updater',
                        '/root/hostfile-updater.sh'
                    ]
                )
            })
        }
    )

    pullClusterKeyInitConfig = cloudformation.InitConfig(
        files={
            '/root/pull-cluster-key.sh': {
                'content': Join('', [
                    '#! /bin/bash\n',
                    'SSH_DIR=~chainer/.ssh\n',
                    'mkdir -p $SSH_DIR\n',
                    'chmod 755 $SSH_DIR\n',
                    'chown chainer:chainer $SSH_DIR\n',
                    'region=$(curl -sL http://169.254.169.254/latest/meta-data/placement/availability-zone | sed -e \'s/.$//\')\n',
                    'CLUSTER_KEY_BUCKET_NAME=', Ref(AssetBucket), '\n',
                    'TMP_DIR=$(mktemp -d)\n',
                    'aws s3 --region $region cp s3://$CLUSTER_KEY_BUCKET_NAME/.ssh/id_rsa $TMP_DIR/id_rsa\n',
                    'aws s3 --region $region cp s3://$CLUSTER_KEY_BUCKET_NAME/.ssh/id_rsa.pub $TMP_DIR/id_rsa.pub\n',
                    'aws s3 --region $region cp s3://$CLUSTER_KEY_BUCKET_NAME/.ssh/authorized_keys $TMP_DIR/authorized_keys\n',
                    'chmod 600 $TMP_DIR/id_rsa\n',
                    'chmod 644 $TMP_DIR/id_rsa.pub\n',
                    'chmod 600 $TMP_DIR/authorized_keys\n',
                    'cat ~ubuntu/.ssh/authorized_keys >> $TMP_DIR/authorized_keys\n'
                    'chown chainer:chainer $TMP_DIR/*\n',
                    'mv $TMP_DIR/* $SSH_DIR/\n',
                    'rm -rf $TMP_DIR\n'
                ]),
                'mode': '000755',
                'owner': 'root',
                'group': 'root'
            },
            '/etc/cron.d/pull-cluster-key': {
                'content': Join('', [
                    'SHELL=/bin/bash\n',
                    'PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin\n',
                    'MAILTO=""\n',
                    'HOME=/\n',
                    '* * * * * root /root/pull-cluster-key.sh\n',
                ]),
                'mode': '000644',
                'owner': 'root',
                'group': 'root'
            }
        },
        commands={
            'pull-cluster-key': {
                'command':'/root/pull-cluster-key.sh'
            }
        },
        services={
            'sysvinit': cloudformation.InitServices({
                "cron": cloudformation.InitService(
                    enabled=True,
                    ensureRunning=True,
                    files=[
                        '/etc/cron.d/pull-cluster-key',
                        '/root/pull-cluster-key.sh'
                    ]
                )
            })
        }
    )

    nfsMountInitConfig = cloudformation.InitConfig(
        commands={
            '01_createdir': {
                'command': Join('', [
                    'mkdir -p /', Ref(EFSMountPoint), '\n'
                ])
            },
            '02_mount': {
                'command': Join('', [
                    'mount -t nfs4 -o nfsvers=4.1 ',
                    targetFileSystem, '.efs.', Region, '.amazonaws.com:/ ',
                    '/', Ref(EFSMountPoint)
                ])
            },
            '03_permissions': {
                'command': Join('', [
                    'chown chainer:chainer /', Ref(EFSMountPoint), '\n',
                ])
            }
        }
    )

    nfsStatInitConfig = cloudformation.InitConfig(
        files={
            '/root/post-nfsstat.sh': {
                'content': Sub(textwrap.dedent('''
                    #!/bin/bash

                    INPUT="$(cat)"
                    CW_JSON_OPEN='{ "Namespace": "EFS", "MetricData": [ '
                    CW_JSON_CLOSE=' ] }'
                    CW_JSON_METRIC=''
                    METRIC_COUNTER=0

                    for COL in 1 2 3 4 5 6; do

                     COUNTER=0
                     METRIC_FIELD=$COL
                     DATA_FIELD=$(($COL+($COL-1)))

                     while read line; do
                       if [[ COUNTER -gt 0 ]]; then

                         LINE=`echo $line | tr -s ' ' `
                         AWS_COMMAND="aws cloudwatch put-metric-data --region ${AWS::Region}"
                         MOD=$(( $COUNTER % 2))

                         if [ $MOD -eq 1 ]; then
                           METRIC_NAME=`echo $LINE | cut -d ' ' -f $METRIC_FIELD`
                         else
                           METRIC_VALUE=`echo $LINE | cut -d ' ' -f $DATA_FIELD`
                         fi

                         if [[ -n "$METRIC_NAME" && -n "$METRIC_VALUE" ]]; then
                           INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
                           CW_JSON_METRIC="$CW_JSON_METRIC { \"MetricName\": \"$METRIC_NAME\", \"Dimensions\": [{\"Name\": \"InstanceId\", \"Value\": \"$INSTANCE_ID\"} ], \"Value\": $METRIC_VALUE },"
                           unset METRIC_NAME
                           unset METRIC_VALUE

                           METRIC_COUNTER=$((METRIC_COUNTER+1))
                           if [ $METRIC_COUNTER -eq 20 ]; then
                             # 20 is max metric collection size, so we have to submit here
                             aws cloudwatch put-metric-data --region ${AWS::Region} --cli-input-json "`echo $CW_JSON_OPEN ${!CW_JSON_METRIC%?} $CW_JSON_CLOSE`"

                             # reset
                             METRIC_COUNTER=0
                             CW_JSON_METRIC=''
                           fi
                         fi



                         COUNTER=$((COUNTER+1))
                       fi

                       if [[ "$line" == "Client nfs v4:" ]]; then
                         # the next line is the good stuff
                         COUNTER=$((COUNTER+1))
                       fi
                     done <<< "$INPUT"
                    done

                    # submit whatever is left
                    aws cloudwatch put-metric-data --region ${AWS::Region} --cli-input-json "`echo $CW_JSON_OPEN ${!CW_JSON_METRIC%?} $CW_JSON_CLOSE`"
                ''').strip()),
                'mode': '000755',
                'owner': 'root',
                'group': 'root'
            },
            '/etc/cron.d/post-nfsstat': {
                'content': Sub(textwrap.dedent('''
                    SHELL=/bin/bash
                    PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin
                    MAILTO=""
                    HOME=/
                    * * * * * root /usr/sbin/nfsstat | /root/post_nfsstat
                ''').strip()),
                'mode': '000644',
                'owner': 'root',
                'group': 'root'
            }
        },
        services={
            'sysvinit': cloudformation.InitServices({
                "cron": cloudformation.InitService(
                    enabled=True,
                    ensureRunning=True,
                    files=[
                        '/etc/cron.d/post-nfsstat',
                        '/root/post-nfsstat.sh'
                    ]
                )
            })
        }
    )

    #
    # Master
    #
    ClusterMasterInstanceProfile = t.add_resource(InstanceProfile(
        "ClusterMasterInstanceProfile",
        Roles=[Ref(ClusterMasterRole)]
    ))

    ClusterMaster = t.add_resource(Instance(
        "ClusterMaster",
        DependsOn=["EFSReadyWaitCondition"],
        ImageId=FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
        InstanceType=Ref(InstanceType),
        KeyName=Ref(KeyPairName),
        IamInstanceProfile=Ref(ClusterMasterInstanceProfile),
        EbsOptimized=True,
        Monitoring=True,
        CreationPolicy=CreationPolicy(
            ResourceSignal=ResourceSignal(
                Timeout='PT30M',
                Count=1
            )
        ),
        SubnetId=targetSubnet,
        SecurityGroupIds=[
            Ref(ClusterMemberMarkerSg),
            Ref(AllowSSHFromExternalSG),
            Ref(AllowAllAmongClusterMember)
        ],
        Tenancy=Ref(InstanceTenancy),
        PlacementGroupName=Ref(ClusterPlacementGroup),
        BlockDeviceMappings=[
            BlockDeviceMapping(
                DeviceName='/dev/sda1',
                Ebs=EBSBlockDevice(
                    VolumeSize=Ref(RootVolumeSize),
                    VolumeType="gp2"
                )
            )
        ],
        Tags=trackingTags + Tags(
            ChainerClusterRole='Master'
        ),
        Metadata=If(
            "EFSEnabled",
            cloudformation.Metadata(
                cloudformation.Init(
                    cloudformation.InitConfigSets(
                        install=[
                            'createChainerUser',
                            'sshClientConfig',
                            'provisionClusterKey',
                            'hostfileUpdater',
                            'nfsMount',
                            'nfsStat'
                        ]
                    ),
                    createChainerUser=createChainerUserInitConfig,
                    sshClientConfig=sshClientConfigInitConfig,
                    provisionClusterKey=provisionClusterKeyInitConfig,
                    hostfileUpdater=hostfileUpdaterInitConfig,
                    nfsMount=nfsMountInitConfig,
                    nfsStat=nfsStatInitConfig
                )
            ),
            cloudformation.Metadata(
                cloudformation.Init(
                    cloudformation.InitConfigSets(
                        install=[
                            'createChainerUser',
                            'sshClientConfig',
                            'provisionClusterKey',
                            'hostfileUpdater',
                        ]
                    ),
                    createChainerUser=createChainerUserInitConfig,
                    sshClientConfig=sshClientConfigInitConfig,
                    provisionClusterKey=provisionClusterKeyInitConfig,
                    hostfileUpdater=hostfileUpdaterInitConfig
                )
            )
        ),
        UserData=Base64(Join('', [
            "#!/bin/bash -xe\n",
            "# Install the files and packages from the metadata\n",
            "/usr/local/bin/cfn-init -v ",
            "         --stack ", StackName,
            "         --resource ClusterMaster",
            "         --configsets install",
            "         --region ", Region, "\n",
            "",
            "/usr/local/bin/cfn-signal -e $? ",
            "         --stack ", StackName,
            "         --resource ClusterMaster ",
            "         --region ", Region, "\n"
        ]))
    ))

    #
    # Worker (Auto Scaling Group)
    #
    ClusterWorkerInstanceProfile = t.add_resource(InstanceProfile(
        "ClusterWorkerInstanceProfile",
        Roles=[Ref(ClusterWorkerRole)]
    ))
    WorkerLC = t.add_resource(LaunchConfiguration(
        "WorkerLC",
        DependsOn=["EFSReadyWaitCondition"],
        ImageId=FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
        InstanceType=Ref(InstanceType),
        KeyName=Ref(KeyPairName),
        IamInstanceProfile=Ref(ClusterWorkerInstanceProfile),
        EbsOptimized=True,
        SecurityGroups=[
            Ref(ClusterMemberMarkerSg),
            Ref(AllowSSHFromExternalSG),
            Ref(AllowAllAmongClusterMember)
        ],
        BlockDeviceMappings=[
            BlockDeviceMapping(
                DeviceName='/dev/sda1',
                Ebs=EBSBlockDevice(
                    VolumeSize=Ref(RootVolumeSize),
                    VolumeType="gp2"
                )
            )
        ],
        Metadata=If(
            "EFSEnabled",
            cloudformation.Metadata(
                cloudformation.Init(
                    cloudformation.InitConfigSets(
                        install=[
                            'createChainerUser',
                            'sshClientConfig',
                            'pullClusterKey',
                            'hostfileUpdater',
                            'nfsMount',
                            'nfsStat'
                        ]
                    ),
                    createChainerUser=createChainerUserInitConfig,
                    sshClientConfig=sshClientConfigInitConfig,
                    pullClusterKey=pullClusterKeyInitConfig,
                    hostfileUpdater=hostfileUpdaterInitConfig,
                    nfsMount=nfsMountInitConfig,
                    nfsStat=nfsStatInitConfig
                )
            ),
            cloudformation.Metadata(
                cloudformation.Init(
                    cloudformation.InitConfigSets(
                        install=[
                            'createChainerUser',
                            'sshClientConfig',
                            'pullClusterKey',
                            'hostfileUpdater',
                        ]
                    ),
                    createChainerUser=createChainerUserInitConfig,
                    sshClientConfig=sshClientConfigInitConfig,
                    pullClusterKey=pullClusterKeyInitConfig,
                    hostfileUpdater=hostfileUpdaterInitConfig,
                )
            ),
        ),
        UserData=Base64(Join('', [
            "#!/bin/bash -xe\n",
            "# Install the files and packages from the metadata\n",
            "/usr/local/bin/cfn-init -v ",
            "         --stack ", StackName,
            "         --resource WorkerLC",
            "         --configsets install",
            "         --region ", Region, "\n",
            "",
            "/usr/local/bin/cfn-signal -e $? ",
            "         --stack ", StackName,
            "         --resource WorkerASG ",
            "         --region ", Region, "\n"
        ]))
    ))

    WorkerASG = t.add_resource(AutoScalingGroup(
        "WorkerASG",
        LaunchConfigurationName=Ref(WorkerLC),
        VPCZoneIdentifier=[targetSubnet],
        PlacementGroup=Ref(ClusterPlacementGroup),
        MinSize=0,
        DesiredCapacity=Ref(WorkerSize),
        MaxSize=Ref(WorkerSize),
        CreationPolicy=CreationPolicy(
            ResourceSignal=ResourceSignal(
                Timeout='PT30M',
                Count=Ref(WorkerSize)
            )
        ),
        MetricsCollection=[MetricsCollection(
            Granularity='1Minute'
        )],
        Tags=troposphere.autoscaling.Tags(
            ChainerClusterName=StackName,
            ChainerClusterRole='Worker'
        )
    ))

    #
    # Outputs
    #
    t.add_output([
        # Output(
        #     "CustmerMusterKey",
        #     Value=Ref(CustomerMasterKey)
        # ),
        Output(
            "AssetBucket",
            Description="Bucket name which cluster sync ssh key for chainer user.  Please make it empty before deleting this stack.",
            Value=Ref(AssetBucket)
        ),
        # Output(
        #     "ClusterKeyLoggingBucket",
        #     Value=Ref(ClusterKeyLoggingBucket)
        # ),
        Output(
            "ClusterMasterPublicDNS",
            Description="Public dns of master instnace of the cluster.  You can login to the instance with either ubuntu(sudo-able) or chainer(sudo-unable) user.",
            Value=GetAtt(ClusterMaster, 'PublicDnsName')
        ),
        Output(
            "EFSFileSystemId",
            Description="Newly created EFS filesystem id.",
            Condition="ShouldCreateEFS",
            Value=Ref(EFSFileSystem)
        ),
        Output(
            "EFSMountTargetId",
            Description="Newly created EFS mount target id.",
            Condition="ShouldCreateEFS",
            Value=Ref(EFSMountTarget)
        ),
        Output(
            "ClusterMemberMarkerSecurityGroup",
            Description="SecurityGroup which all instance in the cluster have.  You can use this source/destination security group when you add some rules to other security groups",
            Value=Ref(ClusterMemberMarkerSg)
        )
    ])
    print(t.to_yaml())


if __name__ == '__main__':
    main()
