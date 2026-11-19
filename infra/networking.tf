### terraform config file to group network resources

# creates a VPC with default range defined by vpc_cidr
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "marketflow-vpc"
  }
}

# creates and attaches an IGW to our VPC
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "marketflow-igw"
  }
}


# creates 2 public subnets in two availability zones for resilient deployment
# cidrsubnet("10.0.0.0/16", 8, 1) --> 10.0.1.0/24 ... 2 makes 10.0.2.0/24

resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 1)   
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true      # give subnet a public IPv4 address

  tags = {
    Name = "marketflow-public-${count.index + 1}"
  }
}

# creates a routing table and assign default route to the IGW
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "marketflow-public-rt"
  }
}

# applies routing table to our 2 subnets
resource "aws_route_table_association" "public" {
  count = 2

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "poller" {
  name        = "marketflow-poller-sg"
  description = "Outbound access for MarketFlow Fargate tasks"
  vpc_id      = aws_vpc.main.id

  egress {    # allow all outbound IPv4 traffic
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "marketflow-poller-sg"
  }
}
