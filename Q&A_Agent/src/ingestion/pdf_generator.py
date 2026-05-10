"""
src/ingestion/pdf_generator.py
───────────────────────────────
Programmatically creates a rich, multi-chapter sample PDF document about
"Fundamentals of Cloud Computing" using ReportLab.

Why ReportLab?
──────────────
ReportLab is a mature, pure-Python PDF library that does not require any
system-level dependencies (no wkhtmltopdf, no LaTeX, no browser engine).
It gives us fine-grained control over page layout, styles, and typography
entirely from Python code — making the generated PDF deterministic and
cross-platform.

Design decisions
────────────────
  • Content is defined as a list of chapter dicts (CHAPTERS) so adding or
    removing content never touches the rendering logic.
  • ReportLab's Platypus "story" model is used rather than the low-level
    canvas API.  Platypus handles page breaks, text flow, and pagination
    automatically — we just describe WHAT to render, not WHERE on the page.
  • Paragraphs within chapter content are separated by double-newlines in
    the source string, then split and individually wrapped in Paragraph
    objects.  This gives ReportLab enough granularity to reflow text
    correctly when the page fills up.

Public API
──────────
    create_sample_pdf(output_path) → Path
"""

import logging
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from observability.logger import get_logger

logger = get_logger(__name__)

# ─── Document metadata ─────────────────────────────────────────────────────────
DOCUMENT_TITLE    = "Fundamentals of Cloud Computing"
DOCUMENT_SUBTITLE = "A Comprehensive Technical Introduction"

# ─── Author photo ─────────────────────────────────────────────────────────────
# Place your headshot at assets/author.png (or .jpg) in the project root.
# The pipeline will embed it on the cover page.  If the file is absent the
# cover renders without the photo — no error is raised.
_BASE = Path(__file__).parent.parent.parent  # project root
AUTHOR_PHOTO_PATH: Path = _BASE / "assets" / "author.png"
AUTHOR_NAME  = "Prakash Pujari"
AUTHOR_LINKEDIN = "linkedin.com/in/prakashpujari1"

# ─── Chapter content ───────────────────────────────────────────────────────────
# Each chapter is a dict with two keys:
#   "heading" — displayed as a styled H1 heading
#   "content" — body text; double-newline characters delineate paragraphs
#
# Content is intentionally educational and original — it serves as the RAG
# source document for Q&A generation.  No real exam questions are included.
CHAPTERS: list[dict] = [
    {
        "heading": "Chapter 1: Introduction to Cloud Computing",
        "content": (
            "Cloud computing is the on-demand delivery of IT resources—including compute power, "
            "storage, databases, networking, software, analytics, and intelligence—over the Internet "
            "to offer faster innovation, flexible resources, and economies of scale. "
            "Instead of buying, owning, and maintaining physical data centers and servers, "
            "organizations can access technology services on an as-needed basis from a cloud provider.\n\n"
            "Cloud computing enables companies to consume compute resources as a utility—just like "
            "electricity—rather than having to build and maintain computing infrastructures in-house. "
            "This shift eliminates the upfront capital expense of buying hardware and software and "
            "setting up and running on-site data centers.\n\n"
            "The National Institute of Standards and Technology (NIST) defines cloud computing "
            "through five essential characteristics:\n\n"
            "On-Demand Self-Service: Users can provision computing capabilities automatically without "
            "requiring human interaction with each service provider.\n\n"
            "Broad Network Access: Capabilities are available over the network and accessed through "
            "standard mechanisms promoting use by heterogeneous thin or thick client platforms.\n\n"
            "Resource Pooling: The provider's computing resources are pooled to serve multiple "
            "consumers using a multi-tenant model, with different physical and virtual resources "
            "dynamically assigned and reassigned according to demand.\n\n"
            "Rapid Elasticity: Capabilities can be elastically provisioned and released to scale "
            "rapidly outward and inward commensurate with demand. To the consumer, the capabilities "
            "available for provisioning often appear unlimited.\n\n"
            "Measured Service: Cloud systems automatically control and optimize resource use by "
            "leveraging a metering capability at some level of abstraction appropriate to the type "
            "of service (e.g., storage, processing, bandwidth, and active user accounts)."
        ),
    },
    {
        "heading": "Chapter 2: Cloud Service Models",
        "content": (
            "Cloud computing services are broadly divided into three main service models: "
            "Infrastructure as a Service (IaaS), Platform as a Service (PaaS), and "
            "Software as a Service (SaaS).\n\n"
            "Infrastructure as a Service (IaaS): IaaS provides virtualized computing resources "
            "over the Internet. In an IaaS model, the cloud provider hosts the infrastructure "
            "components traditionally present in an on-premises data center, including servers, "
            "storage, and networking hardware, as well as the virtualization or hypervisor layer. "
            "IaaS clients have access to virtual machines, networking resources, and storage "
            "solutions. The customer manages the operating system, middleware, runtime, data, and "
            "applications, while the provider manages virtualization, servers, hard drives, storage, "
            "and networking. Examples include Amazon EC2, Google Compute Engine, and Microsoft "
            "Azure Virtual Machines.\n\n"
            "Platform as a Service (PaaS): PaaS removes the need for organizations to manage the "
            "underlying infrastructure (usually hardware and operating systems) and allows focus on "
            "the deployment and management of applications. This improves efficiency because you "
            "don't need to worry about resource procurement, capacity planning, software maintenance, "
            "and patching. PaaS provides a platform allowing customers to develop, run, and manage "
            "applications without the complexity of building and maintaining the infrastructure "
            "typically associated with developing and launching an app. Examples include AWS Elastic "
            "Beanstalk, Google App Engine, and Heroku.\n\n"
            "Software as a Service (SaaS): SaaS provides a complete product run and managed by the "
            "service provider. With a SaaS offering, you don't need to think about how the service "
            "is maintained or how the underlying infrastructure is managed—you only need to think "
            "about how you will use that particular piece of software. Common examples include Gmail, "
            "Salesforce, Microsoft 365, and Dropbox.\n\n"
            "Function as a Service (FaaS) / Serverless: A newer paradigm, FaaS allows developers "
            "to execute code in response to events without managing server infrastructure. The cloud "
            "provider dynamically manages the allocation and provisioning of servers. AWS Lambda, "
            "Azure Functions, and Google Cloud Functions are prominent examples. Serverless "
            "architectures are event-driven and billed purely on execution time and invocations."
        ),
    },
    {
        "heading": "Chapter 3: Cloud Deployment Models",
        "content": (
            "Cloud environments can be deployed in several ways depending on an organization's "
            "needs, security requirements, and budget.\n\n"
            "Public Cloud: A public cloud is owned and operated by a third-party cloud service "
            "provider, which delivers computing resources over the Internet. All hardware, software, "
            "and other supporting infrastructure is owned and managed by the cloud provider. In a "
            "public cloud, you share the same hardware, storage, and network devices with other "
            "organizations—also called cloud tenants. Public cloud deployments are frequently used "
            "for web-based email, online office applications, storage, and testing and development "
            "environments.\n\n"
            "Private Cloud: A private cloud refers to cloud computing resources used exclusively by "
            "a single business or organization. A private cloud can be physically located on the "
            "company's on-site data center or hosted by a third-party service provider. Services and "
            "infrastructure are always maintained on a private network and the hardware and software "
            "are dedicated solely to the organization. Private clouds are often used by government "
            "agencies, financial institutions, and businesses that require greater control over "
            "their environment.\n\n"
            "Hybrid Cloud: Hybrid clouds combine public and private clouds, bound together by "
            "technology that allows data and applications to be shared between them. By allowing "
            "data and applications to move between private and public clouds, a hybrid cloud gives "
            "businesses greater flexibility, more deployment options, and helps optimize existing "
            "infrastructure, security, and compliance.\n\n"
            "Multi-Cloud: Many organizations use multiple cloud providers simultaneously—a "
            "multi-cloud strategy. This approach avoids vendor lock-in, provides geographic "
            "diversity, and allows organizations to choose best-of-breed services from different "
            "providers. A multi-cloud strategy introduces complexity in management, networking, "
            "and security but is increasingly common in large enterprises.\n\n"
            "Community Cloud: A community cloud is shared by several organizations with similar "
            "requirements and objectives. It may be managed internally or by a third party and "
            "can be on-premises or off-premises. It is common in regulated industries such as "
            "healthcare and government."
        ),
    },
    {
        "heading": "Chapter 4: Cloud Security",
        "content": (
            "Security in cloud computing is a shared responsibility between the cloud provider "
            "and the customer—known as the Shared Responsibility Model.\n\n"
            "The Shared Responsibility Model: Under this model, the cloud service provider is "
            "responsible for securing the infrastructure that runs all services offered in the "
            "cloud. This infrastructure is composed of hardware, software, networking, and "
            "facilities. The customer is responsible for the security of the cloud services they "
            "use. In IaaS, customers are responsible for the operating system, network controls, "
            "and applications. In SaaS, customers are primarily responsible for data classification "
            "and management, and user access control.\n\n"
            "Identity and Access Management (IAM): IAM enables organizations to control who is "
            "authenticated (signed in) and authorized (has permissions) to use resources. "
            "Key IAM concepts include the Principle of Least Privilege (users have only the "
            "minimum permissions needed), Multi-Factor Authentication (MFA), and Role-Based Access "
            "Control (RBAC).\n\n"
            "Data Encryption: Data should be encrypted both at rest and in transit. Encryption at "
            "rest protects stored data from unauthorized access, while encryption in transit (TLS) "
            "protects data as it moves between services or between a user and a service. Key "
            "management services (KMS) allow centralized control of cryptographic keys.\n\n"
            "Network Security: Virtual Private Clouds (VPCs), security groups, network access "
            "control lists (NACLs), and Web Application Firewalls (WAFs) are used to secure "
            "the network layer in cloud environments. Zero-trust networking models are increasingly "
            "adopted, where no traffic is trusted by default regardless of its source.\n\n"
            "Compliance and Governance: Cloud providers hold numerous compliance certifications "
            "such as ISO 27001, SOC 2, PCI DSS, and HIPAA. Organizations must ensure their "
            "deployments meet applicable regulatory requirements. Cloud Security Posture Management "
            "(CSPM) tools continuously monitor cloud configurations for compliance violations."
        ),
    },
    {
        "heading": "Chapter 5: Scalability, Availability, and Reliability",
        "content": (
            "One of the primary advantages of cloud computing is the ability to scale resources "
            "up or down based on demand.\n\n"
            "Scalability: Scalability refers to the ability of a system to handle increased "
            "workload. There are two types: Vertical Scaling (Scale Up/Down) adds more power "
            "(CPU, RAM) to an existing machine and has limits based on available hardware sizes. "
            "Horizontal Scaling (Scale Out/In) adds more instances to distribute the workload and "
            "is generally preferred in cloud architectures for virtually unlimited scale.\n\n"
            "Elasticity: Elasticity takes scalability further by automatically scaling resources "
            "up or down in response to real-time demand. Auto-scaling groups, scale sets, and "
            "managed instance groups are examples of elasticity in action. Elasticity reduces "
            "over-provisioning and ensures cost efficiency.\n\n"
            "High Availability (HA): HA refers to systems designed to operate continuously "
            "without failure for extended periods. Key HA concepts include Redundancy (backup "
            "components that take over if primary fails), Failover (automatic switch to a "
            "redundant system), and Availability Zones (isolated locations within a cloud region "
            "providing fault isolation).\n\n"
            "Fault Tolerance: Fault tolerance is the ability of a system to continue operating "
            "correctly even when some components fail. Fault-tolerant systems use redundancy, "
            "checkpointing, and error-correction mechanisms.\n\n"
            "Disaster Recovery (DR): DR involves policies, tools, and procedures to enable "
            "recovery of technology infrastructure following a disaster. Key DR metrics are the "
            "Recovery Time Objective (RTO)—the maximum acceptable time to restore a system—and "
            "the Recovery Point Objective (RPO)—the maximum acceptable amount of data loss "
            "measured in time. Common DR strategies include backup and restore, pilot light, "
            "warm standby, and active-active multi-site.\n\n"
            "Content Delivery Networks (CDNs): CDNs distribute content geographically closer to "
            "end users, reducing latency and improving performance. They cache static assets at "
            "edge locations around the world and are a key component of highly available and "
            "performant cloud architectures."
        ),
    },
    {
        "heading": "Chapter 6: Cloud Cost Management and FinOps",
        "content": (
            "Effective cost management is a critical aspect of operating in the cloud. The "
            "pay-as-you-go model can lead to unexpected costs if not properly managed.\n\n"
            "Pricing Models: Cloud providers offer different pricing models. On-Demand pricing "
            "means you pay for what you use with no upfront commitment—best for unpredictable "
            "workloads. Reserved Instances/Committed Use means you commit to using a certain "
            "amount of resources for a 1 or 3-year term in exchange for a significant discount "
            "(typically 30–72% compared to on-demand). Spot/Preemptible Instances use spare cloud "
            "capacity at a steep discount (up to 90% off) but can be interrupted with short "
            "notice. Savings Plans offer flexible pricing in exchange for a commitment to a "
            "consistent amount of usage.\n\n"
            "Total Cost of Ownership (TCO): TCO analysis compares the total cost of running "
            "workloads in the cloud versus on-premises. It includes not just infrastructure costs "
            "but also labor, facilities, power, cooling, and opportunity costs.\n\n"
            "FinOps: FinOps (Financial Operations) is a practice that brings together technology, "
            "business, and finance professionals to drive financial accountability for cloud "
            "spending. Key FinOps practices include tagging and cost allocation to attribute "
            "spending to teams or products, rightsizing to match instance types to actual workload "
            "requirements, identifying idle and unused resources, implementing auto-scaling, and "
            "using cost anomaly detection tools.\n\n"
            "Cloud Cost Optimization Strategies: Choose appropriate storage tiers (hot, cool, "
            "cold/archive) based on access patterns. Use managed services to reduce operational "
            "overhead. Implement lifecycle policies to automatically transition or delete data. "
            "Monitor and optimize data transfer costs. Use cost management dashboards and budgets "
            "with alerts. Consolidate workloads to improve utilization rates."
        ),
    },
    {
        "heading": "Chapter 7: Containers and Microservices in the Cloud",
        "content": (
            "Containers and microservices architectures have become foundational to modern "
            "cloud-native applications.\n\n"
            "Containers: A container packages an application and all its dependencies together "
            "in an isolated environment, ensuring consistent behavior across different computing "
            "environments. Docker is the most widely used container runtime. Containers are "
            "lightweight compared to virtual machines because they share the host operating "
            "system kernel rather than requiring a full OS per instance.\n\n"
            "Container Orchestration: Managing many containers at scale requires orchestration "
            "platforms. Kubernetes (K8s) is the de facto standard for container orchestration, "
            "providing automated deployment, scaling, and management of containerized applications. "
            "Cloud providers offer managed Kubernetes services such as Amazon EKS, Azure AKS, "
            "and Google GKE, reducing the operational overhead of running Kubernetes.\n\n"
            "Microservices Architecture: Microservices decompose an application into small, "
            "independently deployable services, each responsible for a specific business "
            "capability. Benefits include independent scaling, technology heterogeneity, "
            "resilience (a failure in one service does not bring down others), and faster "
            "deployment cycles. Microservices communicate via APIs, typically using REST or "
            "message queues.\n\n"
            "Service Mesh: A service mesh (e.g., Istio, Linkerd) manages service-to-service "
            "communication in a microservices architecture, providing features such as load "
            "balancing, service discovery, traffic management, and mutual TLS encryption "
            "without requiring changes to application code.\n\n"
            "CI/CD in the Cloud: Continuous Integration and Continuous Delivery pipelines "
            "automate testing and deployment of containerized services. Cloud-native CI/CD "
            "tools such as AWS CodePipeline, Azure DevOps, and Google Cloud Build integrate "
            "with version control systems and container registries to provide end-to-end "
            "automation."
        ),
    },
    {
        "heading": "Chapter 8: Cloud Networking",
        "content": (
            "Networking is a foundational component of any cloud deployment, providing "
            "connectivity between resources and to end users.\n\n"
            "Virtual Private Cloud (VPC): A VPC is a logically isolated section of a public "
            "cloud in which you can launch cloud resources in a virtual network you define. "
            "You control the IP address range, subnets, route tables, and network gateways. "
            "VPCs provide network isolation and security boundary control.\n\n"
            "Subnets: Subnets divide the VPC into smaller network segments. Public subnets "
            "have direct routes to an Internet gateway and are used for internet-facing "
            "resources. Private subnets have no direct internet route and are used for "
            "backend resources such as databases. Resources in private subnets can access "
            "the internet via a Network Address Translation (NAT) gateway.\n\n"
            "Load Balancing: Load balancers distribute incoming traffic across multiple "
            "compute instances to ensure no single instance becomes a bottleneck. Application "
            "Load Balancers (ALB) operate at layer 7 and support path-based and host-based "
            "routing. Network Load Balancers (NLB) operate at layer 4 and handle extremely "
            "high throughput with low latency.\n\n"
            "DNS and Traffic Management: Domain Name System (DNS) services in the cloud "
            "(e.g., Amazon Route 53, Azure DNS) provide highly available and scalable domain "
            "registration and routing. Traffic management policies such as latency-based routing, "
            "geolocation routing, and health-check failover enable sophisticated global "
            "traffic patterns.\n\n"
            "VPN and Direct Connect: Site-to-site VPNs create encrypted tunnels between "
            "on-premises networks and the cloud VPC. Dedicated connection services (AWS Direct "
            "Connect, Azure ExpressRoute) provide private, high-bandwidth, low-latency links "
            "from on-premises facilities to the cloud provider's network, bypassing the "
            "public internet entirely."
        ),
    },
]


# ─── PDF builder ───────────────────────────────────────────────────────────────

def create_sample_pdf(output_path: Path | str) -> Path:
    """
    Generates a multi-chapter sample PDF and saves it to *output_path*.

    Architecture
    ────────────
    Uses ReportLab's Platypus "story" abstraction:
      1. Build a list of Flowable objects (Paragraph, Spacer, HRFlowable, …)
         in the order they should appear on the page — this is the "story".
      2. Call SimpleDocTemplate.build(story) which handles:
           • Page layout and margins
           • Reflowing text to fit column width
           • Automatic page breaks when a page is full

    Style hierarchy
    ────────────────
      title_style    → document title on the cover page
      subtitle_style → sub-heading below the title
      chapter_style  → each chapter heading
      body_style     → body paragraph text with justified alignment

    Args:
        output_path: Destination path for the generated PDF.

    Returns:
        Resolved (absolute) Path of the generated PDF.

    Raises:
        OSError: If the destination directory cannot be created or the
                 file cannot be written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # SimpleDocTemplate handles the overall page geometry.  letter = 8.5×11in.
    # Margins are set to 1 inch on all sides — standard for technical documents.
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    # getSampleStyleSheet() returns a stylesheet with sensible base styles.
    # We create custom subclasses via ParagraphStyle to override specific
    # attributes without having to specify every property from scratch.
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=26,
        leading=32,                          # leading = line height
        textColor=colors.HexColor("#1a237e"),  # dark indigo
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#37474f"),  # dark grey-blue
        spaceAfter=24,
        alignment=TA_CENTER,
    )
    chapter_style = ParagraphStyle(
        "ChapterHeading",
        parent=styles["Heading1"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0d47a1"),  # blue
        spaceBefore=20,
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["Normal"],
        fontSize=10,
        leading=16,
        textColor=colors.HexColor("#212121"),  # near-black
        spaceAfter=10,
        alignment=TA_JUSTIFY,   # justified text looks more professional
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Italic"],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )

    # ── Build the story ────────────────────────────────────────────────────────
    # Each Flowable is consumed in order; Platypus decides where page breaks go.
    story: list = []

    # Cover page
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph(DOCUMENT_TITLE, title_style))
    story.append(Paragraph(DOCUMENT_SUBTITLE, subtitle_style))
    story.append(HRFlowable(width="80%", thickness=2, color=colors.HexColor("#1a237e")))
    story.append(Spacer(1, 0.5 * inch))

    # ── Author block ───────────────────────────────────────────────────────────
    author_name_style = ParagraphStyle(
        "AuthorName",
        parent=styles["Normal"],
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#1a237e"),
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    author_meta_style = ParagraphStyle(
        "AuthorMeta",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0077b5"),  # LinkedIn blue
        alignment=TA_CENTER,
        spaceAfter=16,
    )

    # Embed the author photo if it exists on disk
    if AUTHOR_PHOTO_PATH.exists():
        try:
            photo = Image(str(AUTHOR_PHOTO_PATH), width=1.2 * inch, height=1.2 * inch)
            photo.hAlign = "CENTER"
            story.append(photo)
            story.append(Spacer(1, 0.15 * inch))
        except Exception:  # noqa: BLE001 — never let a missing photo crash the pipeline
            pass

    story.append(Paragraph(f"<b>{AUTHOR_NAME}</b>", author_name_style))
    story.append(Paragraph(AUTHOR_LINKEDIN, author_meta_style))
    story.append(HRFlowable(width="50%", thickness=0.5, color=colors.HexColor("#bbdefb")))
    story.append(Spacer(1, 0.2 * inch))

    story.append(
        Paragraph(
            "This document is intended for educational purposes and serves as the "
            "source material for an AI-powered Q&amp;A generation pipeline.",
            disclaimer_style,
        )
    )
    # Force the first chapter onto a fresh page
    story.append(PageBreak())

    # Chapter pages
    for chapter in CHAPTERS:
        story.append(Paragraph(chapter["heading"], chapter_style))
        # A thin decorative rule under each chapter heading
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#bbdefb")))
        story.append(Spacer(1, 6))

        # Split on double-newline so each logical paragraph becomes its own
        # Paragraph object.  Platypus will then reflow each one independently,
        # avoiding a single monolithic block that fills a page without breaks.
        for para_text in chapter["content"].split("\n\n"):
            cleaned = para_text.strip()
            if cleaned:
                story.append(Paragraph(cleaned, body_style))

        story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    logger.info(
        "Sample PDF created: %s (%d chapters)",
        output_path.resolve(),
        len(CHAPTERS),
    )
    return output_path.resolve()
