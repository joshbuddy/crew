import json
import asyncio
from pitcrew import task
from uuid import uuid4


class DeployPitcrew(task.BaseTask):
    """This example builds and deploys pitcrew.io. It uses s3, cloudfront and acm to deploy
    this website using ssl. """

    async def run(self):
        # make sure the build requirements are installed
        await self.sh("pip install -r requirements-build.txt")
        # create the bucket
        await self.sh("aws s3api create-bucket --bucket pitcrew-site")
        # setup aws & build + upload site
        await asyncio.gather(self.setup_aws(), self.build_and_sync())

    async def setup_aws(self):
        # first find the zone
        zones = json.loads(await self.sh("aws route53 list-hosted-zones"))[
            "HostedZones"
        ]
        zone_id = None
        for zone in zones:
            if zone["Name"] == "pitcrew.io.":
                zone_id = zone["Id"]
                break

        assert zone_id, "no zone_id found for pitcrew.io"

        # setup the certificate
        cert_arn = await self.setup_acm(zone_id)
        # setup the CDN
        cf_id = await self.setup_cloudfront(zone_id, cert_arn)
        dist = json.loads(
            await self.sh(f"aws cloudfront get-distribution --id {self.esc(cf_id)}")
        )["Distribution"]
        domain_name = dist["DomainName"]

        # add the DNS records
        await self.ensure.aws.route53.has_records(
            zone_id,
            [
                {
                    "Name": "pitcrew.io.",
                    "Type": "A",
                    "AliasTarget": {
                        "HostedZoneId": "Z2FDTNDATAQYW2",
                        "DNSName": f"{domain_name}.",
                        "EvaluateTargetHealth": False,
                    },
                },
                {
                    "Name": "pitcrew.io.",
                    "Type": "AAAA",
                    "AliasTarget": {
                        "HostedZoneId": "Z2FDTNDATAQYW2",
                        "DNSName": f"{domain_name}.",
                        "EvaluateTargetHealth": False,
                    },
                },
                {
                    "Name": "www.pitcrew.io.",
                    "Type": "CNAME",
                    "TTL": 300,
                    "ResourceRecords": [{"Value": domain_name}],
                },
            ],
        )

    async def setup_acm(self, zone_id) -> str:
        # look for the certificate
        certs = json.loads(
            await self.sh("aws acm list-certificates --certificate-statuses ISSUED")
        )["CertificateSummaryList"]
        for cert in certs:
            if cert["DomainName"] == "pitcrew.io":
                return cert["CertificateArn"]

        # if it doesn't exist, create it
        arn = json.loads(
            await self.sh(
                f"aws acm request-certificate --domain-name pitcrew.io --validation-method DNS --subject-alternative-names {self.esc('*.pitcrew.io')}"
            )
        )["CertificateArn"]
        cert_description = json.loads(
            await self.sh(
                f"aws acm describe-certificate --certificate-arn {self.esc(arn)}"
            )
        )

        validation = cert_description["Certificate"]["DomainValidationOptions"][0]
        await self.ensure.aws.route53.has_records(
            zone_id,
            [
                {
                    "Name": validation["ResourceRecord"]["Name"],
                    "Type": validation["ResourceRecord"]["Type"],
                    "TTL": 60,
                    "ResourceRecords": [
                        {"Value": validation["ResourceRecord"]["Value"]}
                    ],
                }
            ],
        )

        await self.sh(
            f"aws acm wait certificate-validated --certificate-arn {self.esc(arn)}"
        )
        return arn

    async def setup_cloudfront(self, zone_id, cert_arn) -> str:
        s3_origin = "pitcrew-site.s3.amazonaws.com"

        list_distributions = json.loads(
            await self.sh(f"aws cloudfront list-distributions")
        )
        for dist in list_distributions["DistributionList"]["Items"]:
            if dist["Origins"]["Items"][0]["DomainName"] == s3_origin:
                return dist["Id"]

        config = {
            "DefaultRootObject": "index.html",
            "Aliases": {"Quantity": 2, "Items": ["pitcrew.io", "www.pitcrew.io"]},
            "Origins": {
                "Quantity": 1,
                "Items": [
                    {
                        "Id": "pitcrew-origin",
                        "DomainName": s3_origin,
                        "S3OriginConfig": {"OriginAccessIdentity": ""},
                    }
                ],
            },
            "DefaultCacheBehavior": {
                "TargetOriginId": "pitcrew-origin",
                "ForwardedValues": {
                    "QueryString": True,
                    "Cookies": {"Forward": "none"},
                },
                "TrustedSigners": {"Enabled": False, "Quantity": 0},
                "ViewerProtocolPolicy": "redirect-to-https",
                "MinTTL": 180,
            },
            "CallerReference": str(uuid4()),
            "Comment": "Created by crew",
            "Enabled": True,
            "ViewerCertificate": {
                "ACMCertificateArn": cert_arn,
                "SSLSupportMethod": "sni-only",
            },
        }
        create_distribution = json.loads(
            await self.sh(
                f"aws cloudfront create-distribution --distribution-config {self.esc(json.dumps(config))}"
            )
        )
        cf_id = create_distribution["Distribution"]["Id"]
        await self.sh(f"aws cloudfront wait distribution-deployed --id {cf_id}")
        return cf_id

    async def build_and_sync(self):
        await self.examples.deploy_pitcrew.build()
        await self.sh("aws s3 sync --acl public-read out/ s3://pitcrew-site/")
