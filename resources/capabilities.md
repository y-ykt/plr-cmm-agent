# The 16 PLR-CMM capabilities (Section III of the PLR-CMM paper, verbatim)

The definitions used for judging are these 16. Each capability heading gives its ID and the short name used in Table II of the paper; the text under it is the paper's own wording.

## Level 1: Trust Foundation

This level comprises three capabilities for designing the prerequisites for trust.

### C1-1 Clarify research objectives and data requirements

Primary PDT variable: Purpose.

The first capability (C1-1) is the ability to clarify research objectives and data requirements. It positions the purpose of data utilization within contextual objectives, such as research, healthcare, the public good, or private use, and organizes the types, granularity, and collection period of the data.

### C1-2 Define a data catalog and establish it as a common language

Primary PDT variable: Purpose.

The second capability (C1-2) is defining a data catalog and establishing it as a common language. Data items are defined in catalog form and maintained as a common language between data providers and users.

### C1-3 Understand legal and regulatory requirements and translate them into functional requirements

Primary PDT variable: Trust.

The third capability (C1-3) is understanding legal and regulatory requirements and translating them into functional requirements. Requirements imposed by regulations, such as GDPR, APPI, and HIPAA, including prohibitions on use beyond the intended purpose and restrictions on third-party provision, can be translated into functional requirements, such as consent acquisition workflows and application programming interface (API) design.

## Level 2: Trust Building

This level comprises three capabilities for supporting trust through the consent process.

### C2-1 Identify stakeholders and define their roles

Primary PDT variable: Trustee.

The first capability (C2-1) is identifying stakeholders and defining their roles. It clearly specifies the roles of the four stakeholder groups, comprising data subjects, primary users, secondary users, and intermediaries, while identifying the ethical tensions and trust requirements that exist among them.

### C2-2 Obtain context-dependent consent

Primary PDT variable: Trust.

The second capability (C2-2) is obtaining context-dependent consent. The system can obtain and manage explicit consent for each individual transaction by presenting contextual information, such as purpose, type, and duration of data use. This capability also includes the scalable and repeated operation of identity verification using electronic Know Your Customer (eKYC) and public personal authentication services.

### C2-3 Select and evolve the consent model

Primary PDT variable: Purpose.

The third capability (C2-3) is selecting and evolving the consent model. Beginning with an initial transaction-by-transaction consent model, this capability enables the design and operation of hybrid consent models, such as broad consent with withdrawal rights, that balance legal compliance with usability while addressing human limitations, such as consent fatigue.

## Level 3: Trust Scaling

This level comprises three capabilities for establishing governance that preserves trust as operations scale.

### C3-1 Institutionalize review and governance across multiple projects

Primary PDT variable: Trust.

The first capability (C3-1) is institutionalizing review and governance across multiple projects. It includes conducting reviews from the perspective of ethical, legal, and social issues (ELSI) and obtaining third-party certifications.

### C3-2 Distributed governance and security design

Primary PDT variable: Trust.

The second capability (C3-2) is distributed governance and security design. It enables the implementation of a distributed management model in which the actual data remain under the control of primary users while intermediaries specialize in catalogs and access control to reduce the attack surface.

### C3-3 Operate in a manner that withstands system evolution and migration

Primary PDT variable: Trust.

The third capability (C3-3) is operating in a manner that withstands system evolution and migration. Operations can continue without compromising data integrity or trust relationships even when systems are migrated between different vendors or architectures are changed.

## Level 4: Trust Reciprocation

This level comprises three capabilities for moving beyond one-way data provision and establishing mechanisms through which value circulates among data subjects, primary users, and secondary users.

### C4-1 Complete data transactions

Primary PDT variable: Trust.

The first capability (C4-1) is completing data transactions. It enables the full execution of the end-to-end process, including concluding usage agreements, providing data, and distributing compensation. It also enables the design of incentives for data subjects that encompass not only monetary value but also fulfillment gained through contributing to society and participating in research, while implementing feedback loops within the system.

### C4-2 Return the outcomes of the intended purpose to data subjects

Primary PDT variable: Trust.

The second capability (C4-2) is returning the outcomes of the intended purpose to data subjects. It enables the design and implementation of value circulation scenarios by incorporating data submission and notification pathways that return analytical results and knowledge obtained through secondary use to data subjects and primary users.

### C4-3 Identify and address semantic gaps

Primary PDT variable: Purpose.

The third capability (C4-3) is identifying and addressing semantic gaps. It enables the continuous and agile evolution of catalog structures by reorganizing data catalogs that were originally created from the perspective of primary users into forms that secondary users can search more easily. Incorporating consent management for catalog items enables metadata and catalogs to be managed in a one-to-many relationship, allowing them to serve as a common language shared by all stakeholders.

## Level 5: Trust Inclusion

This level comprises four capabilities for realizing a data ecosystem that supports participation by people with diverse needs through a chain of trust.

### C5-1 Systematic removal of participation barriers

Primary PDT variable: Trustee.

The first capability (C5-1) is the systematic removal of participation barriers. Even people with limited decision-making or operational abilities can participate in the ecosystem.

### C5-2 Operate proxy participation and delegation

Primary PDT variable: Trust.

The second capability (C5-2) is operating proxy participation and delegation. Representatives such as family members, facility administrators, or artificial intelligence (AI) agents can provide consent or act under delegation based on a chain of trust for data subjects who, for various reasons, have difficulty expressing their own consent. The intermediary, acting through the representative, provides mechanisms to preserve the data subject’s control and to fulfill accountability for the status of data provision.

### C5-3 Connection through interoperability

Primary PDT variable: Trustee.

The third capability (C5-3) is connection through interoperability. Standardized connection specifications can establish an environment that supports federation with other PLR implementations, information banks, public databases, and similar systems.

### C5-4 Operate a sustainable data-provision ecosystem

Primary PDT variable: Trustee.

The fourth capability (C5-4) is operation of a sustainable data-provision ecosystem. Transactions with multiple data users can proceed through standardized processes so that the ecosystem can be sustained with defined operational roles, funding, and review.

## Criterion in the paper (Section IV-A, verbatim)

Within this model, a capability is categorized as acquired if it has been demonstrated in at least one study and subsequently used in routine operation, and as partially acquired when it has been demonstrated only under specific conditions or has not yet entered routine operation.

In this procedure, whether a capability was subsequently used in routine operation is not judged from the records of a single study (see procedure.md, decision 3).
