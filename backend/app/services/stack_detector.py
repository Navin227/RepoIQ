from pathlib import Path
from typing import Dict, List, Any, Set
import json
import logging
import re

logger = logging.getLogger(__name__)


class TechDetection:
    def __init__(self, name: str, source: str, evidence: str, confidence: int = 100):
        self.name = name
        self.source = source
        self.evidence = evidence
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "evidence": self.evidence,
            "confidence": self.confidence
        }


class StackDetector:
    def __init__(self):
        self.languages: Set[str] = set()
        self.technologies: List[TechDetection] = []
        self.seen_techs: Set[tuple] = set()

    def _add_technology(self, detection: TechDetection):
        key = (detection.name, detection.source)
        if key not in self.seen_techs:
            self.seen_techs.add(key)
            self.technologies.append(detection)
            logger.debug(f"✓ Detected: {detection.name} from {detection.source} - {detection.evidence}")

    def detect(self, scan: dict) -> Dict[str, Any]:
        self.languages = set()
        self.technologies = []
        self.seen_techs = set()
        files = scan.get("files", [])
        dependencies = scan.get("dependencies", {})

        logger.debug(f"🔍 Starting technology detection...")
        logger.debug(f"📁 Files to scan: {len(files)}")
        logger.debug(f"📦 Dependency files found: {len(dependencies)}")

        # Log all discovered package.json files
        package_json_files = [path for path in dependencies.keys() if path.endswith("package.json")]
        if package_json_files:
            logger.debug(f"📦 Found {len(package_json_files)} package.json file(s):")
            for pj in package_json_files:
                logger.debug(f"   - {pj} (Size: {len(str(dependencies[pj].get('content', '')))} chars)")
        else:
            logger.debug("⚠️  No package.json files found!")

        # STAGE 1: Detect Languages
        self._stage1_detect_languages(files)
        logger.debug(f"🔤 Languages detected: {sorted(list(self.languages))}")

        # STAGE 2: Detect Frameworks and Tools
        self._stage2_detect_technologies(dependencies, files)
        logger.debug(f"🔧 Total technologies detected: {len(self.technologies)}")

        # STAGE 3: Aggregate and Categorize Technologies
        categories = self._stage3_categorize_and_aggregate()

        # Log category summary
        for cat_name, techs in categories.items():
            if techs:
                logger.debug(f"📂 {cat_name.upper()}: {len(techs)} technologies")
                for tech in techs:
                    logger.debug(f"   - {tech['name']} (found in {tech['count']} file(s))")
            else:
                logger.debug(f"⚠️  {cat_name.upper()}: EMPTY - No technologies detected in this category")

        # Add flat list for backwards compatibility
        flat = {cat: list({d["name"] for d in techs}) for cat, techs in categories.items()}
        
        logger.debug("🔍 Final Technology Stack Summary:")
        logger.debug(json.dumps(flat, indent=2))

        result = {
            "languages": sorted(list(self.languages)),
            "categories": categories,
            "flat": flat
        }

        logger.debug(f"✅ Detection complete. Result: {len(self.languages)} languages, {len(self.technologies)} tech detections")
        return result

    def _stage1_detect_languages(self, files: list[str]):
        ext_to_lang = {
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".py": "Python",
            ".go": "Go",
            ".java": "Java",
            ".kt": "Kotlin",
            ".rs": "Rust",
            ".cs": "C#",
            ".php": "PHP",
            ".rb": "Ruby",
            ".c": "C",
            ".cpp": "C++",
            ".cc": "C++",
            ".swift": "Swift",
            ".dart": "Dart",
            ".scala": "Scala",
            ".ex": "Elixir",
            ".exs": "Elixir",
            ".tf": "HCL"
        }

        for file in files:
            path = Path(file)
            if path.suffix in ext_to_lang:
                self.languages.add(ext_to_lang[path.suffix])

        # Also check build files to add languages
        for file in files:
            if file.endswith("go.mod"):
                self.languages.add("Go")
            elif file.endswith("Cargo.toml"):
                self.languages.add("Rust")
            elif file.endswith("pom.xml") or file.endswith("build.gradle") or file.endswith("build.gradle.kts"):
                self.languages.add("Java")
            elif file.endswith("composer.json"):
                self.languages.add("PHP")
            elif file.endswith("Gemfile"):
                self.languages.add("Ruby")
            elif file.endswith("mix.exs"):
                self.languages.add("Elixir")
            elif file.endswith("build.sbt"):
                self.languages.add("Scala")
            elif file.endswith("pubspec.yaml"):
                self.languages.add("Dart")

    def _stage2_detect_technologies(self, dependencies: dict, files: list[str]):
        for rel_path, dep_data in dependencies.items():
            dep_type = dep_data.get("type", "")
            content = dep_data.get("content", "")

            if dep_type == "package.json":
                logger.debug(f"📦 Processing package.json: {rel_path}")
                pkg_data = content
                if isinstance(content, str):
                    try:
                        pkg_data = json.loads(content)
                        logger.debug(f"✅ Successfully parsed package.json string from {rel_path}")
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Failed to parse package.json at {rel_path}: {e}")
                        continue
                
                if isinstance(pkg_data, dict):
                    self._detect_from_package_json(rel_path, pkg_data)
                else:
                    logger.debug(f"⚠️  package.json content is not a dict after parsing: {type(pkg_data)}")

            elif dep_type == "requirements.txt" and isinstance(content, list):
                self._detect_from_requirements_txt(rel_path, content)
            elif dep_type == "pyproject.toml":
                content_lower = str(content).lower()
                if "[tool.poetry]" in content_lower:
                    self._add_technology(TechDetection("Poetry", rel_path, "Poetry config found"))
                if "django" in content_lower:
                    self._add_technology(TechDetection("Django", rel_path, "Django in pyproject.toml"))
                if "fastapi" in content_lower:
                    self._add_technology(TechDetection("FastAPI", rel_path, "FastAPI in pyproject.toml"))
                if "flask" in content_lower:
                    self._add_technology(TechDetection("Flask", rel_path, "Flask in pyproject.toml"))
            elif dep_type == "go.mod":
                content_lower = str(content).lower()
                if "github.com/gin-gonic/gin" in content_lower:
                    self._add_technology(TechDetection("Gin", rel_path, "Gin framework found"))
                if "github.com/gofiber/fiber" in content_lower:
                    self._add_technology(TechDetection("Fiber", rel_path, "Fiber framework found"))
                if "github.com/labstack/echo" in content_lower:
                    self._add_technology(TechDetection("Echo", rel_path, "Echo framework found"))
                if "github.com/go-redis/redis" in content_lower:
                    self._add_technology(TechDetection("Redis", rel_path, "Go Redis library found"))
                if "gorm.io/gorm" in content_lower:
                    self._add_technology(TechDetection("GORM", rel_path, "GORM ORM found"))
                if "github.com/go-sql-driver/mysql" in content_lower:
                    self._add_technology(TechDetection("MySQL", rel_path, "Go MySQL driver found"))
                if "github.com/lib/pq" in content_lower:
                    self._add_technology(TechDetection("PostgreSQL", rel_path, "Go PostgreSQL driver found"))
                if "github.com/mongodb/mongo-go-driver" in content_lower:
                    self._add_technology(TechDetection("MongoDB", rel_path, "Go MongoDB driver found"))
            elif dep_type == "java-build":
                content_lower = str(content).lower()
                if "spring-boot" in content_lower or "springframework" in content_lower:
                    self._add_technology(TechDetection("Spring Boot", rel_path, "Spring Boot found"))
                if "hibernate" in content_lower:
                    self._add_technology(TechDetection("Hibernate", rel_path, "Hibernate found"))
                if "postgresql" in content_lower:
                    self._add_technology(TechDetection("PostgreSQL", rel_path, "PostgreSQL in Java build file"))
                if "mysql" in content_lower:
                    self._add_technology(TechDetection("MySQL", rel_path, "MySQL in Java build file"))
                if "elasticsearch" in content_lower:
                    self._add_technology(TechDetection("Elasticsearch", rel_path, "Elasticsearch in Java build file"))
                if "maven" in rel_path.lower():
                    self._add_technology(TechDetection("Maven", rel_path, "Maven used"))
            elif dep_type in ("dockerfile", "docker-compose"):
                content_lower = str(content).lower()
                self._add_technology(TechDetection("Docker", rel_path, "Dockerfile/docker-compose file found"))
                if "podman" in content_lower:
                    self._add_technology(TechDetection("Podman", rel_path, "Podman found"))

                if "postgres" in content_lower:
                    self._add_technology(TechDetection("PostgreSQL", rel_path, "PostgreSQL service found in docker config"))
                if "mysql" in content_lower:
                    self._add_technology(TechDetection("MySQL", rel_path, "MySQL service found in docker config"))
                if "mariadb" in content_lower:
                    self._add_technology(TechDetection("MariaDB", rel_path, "MariaDB service found in docker config"))
                if "mongodb" in content_lower or "mongo" in content_lower:
                    self._add_technology(TechDetection("MongoDB", rel_path, "MongoDB service found in docker config"))
                if "redis" in content_lower:
                    self._add_technology(TechDetection("Redis", rel_path, "Redis service found in docker config"))
                if "elasticsearch" in content_lower:
                    self._add_technology(TechDetection("Elasticsearch", rel_path, "Elasticsearch service found in docker config"))
                if "opensearch" in content_lower:
                    self._add_technology(TechDetection("OpenSearch", rel_path, "OpenSearch service found in docker config"))
                if "cassandra" in content_lower:
                    self._add_technology(TechDetection("Cassandra", rel_path, "Cassandra service found in docker config"))
                if "memcached" in content_lower:
                    self._add_technology(TechDetection("Memcached", rel_path, "Memcached service found in docker config"))
                if "kafka" in content_lower:
                    self._add_technology(TechDetection("Kafka", rel_path, "Kafka service found in docker config"))
                if "rabbitmq" in content_lower:
                    self._add_technology(TechDetection("RabbitMQ", rel_path, "RabbitMQ service found in docker config"))
                if "prometheus" in content_lower:
                    self._add_technology(TechDetection("Prometheus", rel_path, "Prometheus service found in docker config"))
                if "grafana" in content_lower:
                    self._add_technology(TechDetection("Grafana", rel_path, "Grafana service found in docker config"))
            elif dep_type == "terraform":
                content_lower = str(content).lower()
                self._add_technology(TechDetection("Terraform", rel_path, "Terraform config file found"))

                # Cloud providers are detected from Terraform provider/resource names,
                # not broad text keywords.
                if self._has_tf_resource(content_lower, "aws_"):
                    self._add_technology(TechDetection("AWS", rel_path, "AWS Terraform resources found"))
                if self._has_tf_resource(content_lower, "google_"):
                    self._add_technology(TechDetection("GCP", rel_path, "Google Cloud Terraform resources found"))
                if self._has_tf_resource(content_lower, "azurerm_"):
                    self._add_technology(TechDetection("Azure", rel_path, "Azure Terraform resources found"))
                if self._has_tf_resource(content_lower, "cloudflare_"):
                    self._add_technology(TechDetection("Cloudflare", rel_path, "Cloudflare Terraform resources found"))

                # AWS Services
                if self._has_tf_resource(content_lower, "aws_sqs_queue"):
                    self._add_technology(TechDetection("SQS", rel_path, "aws_sqs_queue found"))
                if self._has_tf_resource(content_lower, "aws_sns_topic"):
                    self._add_technology(TechDetection("SNS", rel_path, "aws_sns_topic found"))
                if self._has_tf_resource(content_lower, "aws_lambda_function"):
                    self._add_technology(TechDetection("Lambda", rel_path, "AWS Lambda found"))
                if self._has_tf_resource(content_lower, "aws_s3_bucket") or self._has_tf_resource(content_lower, "aws_s3_object"):
                    self._add_technology(TechDetection("S3", rel_path, "AWS S3 found"))
                if self._has_tf_resource(content_lower, "aws_dynamodb_table"):
                    self._add_technology(TechDetection("DynamoDB", rel_path, "DynamoDB found"))
                if self._has_tf_resource(content_lower, "aws_rds_cluster") or self._has_tf_resource(content_lower, "aws_db_instance"):
                    self._add_technology(TechDetection("RDS", rel_path, "AWS RDS found"))
                if self._has_tf_resource(content_lower, "aws_eks_cluster"):
                    self._add_technology(TechDetection("EKS", rel_path, "AWS EKS found"))
                if self._has_tf_resource(content_lower, "aws_ecs_cluster"):
                    self._add_technology(TechDetection("ECS", rel_path, "AWS ECS found"))
                if self._has_tf_resource(content_lower, "aws_api_gateway_") or self._has_tf_resource(content_lower, "aws_apigatewayv2_"):
                    self._add_technology(TechDetection("API Gateway", rel_path, "AWS API Gateway found"))
                if self._has_tf_resource(content_lower, "aws_cognito_"):
                    self._add_technology(TechDetection("Cognito", rel_path, "AWS Cognito found"))
                if self._has_tf_resource(content_lower, "aws_cloudwatch_"):
                    self._add_technology(TechDetection("CloudWatch", rel_path, "AWS CloudWatch found"))
                
                # GCP Services
                if self._has_tf_resource(content_lower, "google_cloud_run_service"):
                    self._add_technology(TechDetection("Cloud Run", rel_path, "Cloud Run found"))
                if self._has_tf_resource(content_lower, "google_container_cluster"):
                    self._add_technology(TechDetection("GKE", rel_path, "GKE found"))
                
                # Azure Services
                if self._has_tf_resource(content_lower, "azurerm_kubernetes_cluster"):
                    self._add_technology(TechDetection("AKS", rel_path, "AKS found"))
            elif dep_type in ("yaml", "kubernetes", "helm", "kustomize"):
                content_lower = str(content).lower()

                k8s_kinds = [
                    "kind: deployment", "kind: service", "kind: ingress",
                    "kind: statefulset", "kind: daemonset", "kind: configmap",
                    "kind: secret", "kind: pod", "kind: namespace",
                    "kind: replicaset", "kind: deploymentconfig", "kind: route"
                ]
                if any(kind in content_lower for kind in k8s_kinds):
                    self._add_technology(TechDetection("Kubernetes", rel_path, "Kubernetes manifest found"))

                if dep_type == "helm" or "chart.yaml" in rel_path.lower() or "values.yaml" in rel_path.lower():
                    self._add_technology(TechDetection("Helm", rel_path, "Helm chart found"))

                if dep_type == "kustomize":
                    self._add_technology(TechDetection("Kustomize", rel_path, "Kustomize config found"))

                if "argocd" in content_lower or ("application" in content_lower and "project" in content_lower):
                    self._add_technology(TechDetection("ArgoCD", rel_path, "ArgoCD config found"))

                if "argoworkflows" in content_lower or ("workflow" in content_lower and "templates" in content_lower):
                    self._add_technology(TechDetection("Argo Workflows", rel_path, "Argo Workflows found"))
            elif dep_type in ("github-actions", "gitlab-ci", "jenkins", "circleci"):
                if dep_type == "github-actions":
                    self._add_technology(TechDetection("GitHub Actions", rel_path, "GitHub Actions workflow found"))
                elif dep_type == "gitlab-ci":
                    self._add_technology(TechDetection("GitLab CI", rel_path, "GitLab CI config found"))
                elif dep_type == "jenkins":
                    self._add_technology(TechDetection("Jenkins", rel_path, "Jenkinsfile found"))
                elif dep_type == "circleci":
                    self._add_technology(TechDetection("CircleCI", rel_path, "CircleCI config found"))
            elif dep_type == "monitoring":
                content_lower = str(content).lower()
                if "prometheus" in rel_path.lower() or "prometheus" in content_lower:
                    self._add_technology(TechDetection("Prometheus", rel_path, "Prometheus config found"))
                if "grafana" in rel_path.lower() or "grafana" in content_lower:
                    self._add_technology(TechDetection("Grafana", rel_path, "Grafana config found"))

    def _detect_from_package_json(self, path: str, deps: Dict):
        """Detect technologies from package.json dependencies"""
        all_deps = {}
        
        # Merge all dependency types
        for key in ["dependencies", "devDependencies", "peerDependencies"]:
            if key in deps and isinstance(deps[key], dict):
                all_deps.update({str(k).lower(): v for k, v in deps[key].items()})

        if not all_deps:
            metadata_keys = {
                "name", "version", "private", "type", "scripts", "main", "module",
                "exports", "license", "description", "author", "repository", "keywords",
                "engines", "browser", "bin", "files"
            }
            all_deps.update({
                str(k).lower(): v
                for k, v in deps.items()
                if k not in metadata_keys and isinstance(v, str)
            })

        logger.debug(f"📝 Scanning {path}: {len(all_deps)} dependencies found")
        logger.debug(f"   Deps: {list(all_deps.keys())}")

        # Frontend Frameworks
        if "react" in all_deps or "react-dom" in all_deps:
            self._add_technology(TechDetection("React", path, "react/react-dom dependency found"))
        if "next" in all_deps:
            self._add_technology(TechDetection("Next.js", path, "next dependency found"))
        if "vue" in all_deps:
            self._add_technology(TechDetection("Vue", path, "vue dependency found"))
        if "nuxt" in all_deps:
            self._add_technology(TechDetection("Nuxt", path, "nuxt dependency found"))
        if "@angular/core" in all_deps:
            self._add_technology(TechDetection("Angular", path, "@angular/core dependency found"))
        if "svelte" in all_deps or "@sveltejs/kit" in all_deps:
            self._add_technology(TechDetection("Svelte", path, "svelte dependency found"))
        if "solid-js" in all_deps:
            self._add_technology(TechDetection("SolidJS", path, "solid-js dependency found"))
        if "astro" in all_deps:
            self._add_technology(TechDetection("Astro", path, "astro dependency found"))
        if "@remix-run/react" in all_deps or "remix" in all_deps:
            self._add_technology(TechDetection("Remix", path, "Remix dependency found"))
        if "@builder.io/qwik" in all_deps or "qwik" in all_deps:
            self._add_technology(TechDetection("Qwik", path, "Qwik dependency found"))

        # Build Tools (Tooling, NOT Frontend)
        if "vite" in all_deps:
            self._add_technology(TechDetection("Vite", path, "vite dependency found"))
        if "webpack" in all_deps or "webpack-cli" in all_deps:
            self._add_technology(TechDetection("Webpack", path, "webpack dependency found"))
        if "rollup" in all_deps:
            self._add_technology(TechDetection("Rollup", path, "rollup dependency found"))
        if "parcel" in all_deps:
            self._add_technology(TechDetection("Parcel", path, "parcel dependency found"))
        if "@turbo/pack" in all_deps:
            self._add_technology(TechDetection("TurboPack", path, "TurboPack dependency found"))

        # Package Managers
        if "npm" in all_deps:
            self._add_technology(TechDetection("npm", path, "npm mentioned"))
        if "yarn" in all_deps:
            self._add_technology(TechDetection("Yarn", path, "yarn dependency found"))
        if "pnpm" in all_deps:
            self._add_technology(TechDetection("pnpm", path, "pnpm dependency found"))
        if "bun" in all_deps:
            self._add_technology(TechDetection("bun", path, "bun dependency found"))

        # UI Libraries (Tooling)
        if any(k for k in all_deps if "tailwindcss" in k):
            self._add_technology(TechDetection("TailwindCSS", path, "tailwindcss dependency found"))
        if "@mui/material" in all_deps or "material-ui" in all_deps:
            self._add_technology(TechDetection("Material UI", path, "Material UI dependency found"))
        if "redux" in all_deps or "@reduxjs/toolkit" in all_deps:
            self._add_technology(TechDetection("Redux", path, "redux dependency found"))
        if "zustand" in all_deps:
            self._add_technology(TechDetection("Zustand", path, "zustand dependency found"))
        if "@tanstack/react-query" in all_deps:
            self._add_technology(TechDetection("React Query", path, "@tanstack/react-query dependency found"))

        # Backend Frameworks
        if "express" in all_deps:
            self._add_technology(TechDetection("Express", path, "express dependency found"))
        if "@nestjs/core" in all_deps:
            self._add_technology(TechDetection("NestJS", path, "@nestjs/core dependency found"))

        # ORMs and Database Clients
        if "prisma" in all_deps:
            self._add_technology(TechDetection("Prisma", path, "prisma dependency found"))
        if "typeorm" in all_deps:
            self._add_technology(TechDetection("TypeORM", path, "typeorm dependency found"))
        if "sequelize" in all_deps:
            self._add_technology(TechDetection("Sequelize", path, "sequelize dependency found"))
        if "drizzle-orm" in all_deps:
            self._add_technology(TechDetection("Drizzle", path, "drizzle-orm dependency found"))
        if "mongoose" in all_deps:
            self._add_technology(TechDetection("Mongoose", path, "mongoose dependency found"))
        if "mongodb" in all_deps:
            self._add_technology(TechDetection("MongoDB", path, "mongodb dependency found"))
        if "mysql" in all_deps or "mysql2" in all_deps:
            self._add_technology(TechDetection("MySQL", path, "mysql dependency found"))
        if "pg" in all_deps or "postgresql" in all_deps:
            self._add_technology(TechDetection("PostgreSQL", path, "pg/postgresql dependency found"))
        if "redis" in all_deps or "ioredis" in all_deps:
            self._add_technology(TechDetection("Redis", path, "redis dependency found"))
        if "sqlite3" in all_deps:
            self._add_technology(TechDetection("SQLite", path, "sqlite3 dependency found"))
        if "mariadb" in all_deps:
            self._add_technology(TechDetection("MariaDB", path, "mariadb dependency found"))
        if "elasticsearch" in all_deps or "@elastic/elasticsearch" in all_deps:
            self._add_technology(TechDetection("Elasticsearch", path, "Elasticsearch dependency found"))
        if "meilisearch" in all_deps:
            self._add_technology(TechDetection("Meilisearch", path, "Meilisearch dependency found"))
        if "algoliasearch" in all_deps:
            self._add_technology(TechDetection("Algolia", path, "Algolia dependency found"))

        # Cloud SDKs
        if any(k for k in all_deps if "aws-sdk" in k or "@aws-sdk" in k):
            self._add_technology(TechDetection("AWS", path, "AWS SDK dependency found"))
        if any(k for k in all_deps if "azure" in k or "@azure" in k):
            self._add_technology(TechDetection("Azure", path, "Azure SDK dependency found"))
        if any(k for k in all_deps if "google-cloud" in k or "@google-cloud" in k):
            self._add_technology(TechDetection("GCP", path, "Google Cloud SDK dependency found"))
        if "firebase" in all_deps:
            self._add_technology(TechDetection("Firebase", path, "Firebase dependency found"))
        if "cloudflare" in all_deps or "@cloudflare/workers-sdk" in all_deps:
            self._add_technology(TechDetection("Cloudflare", path, "Cloudflare dependency found"))

        # Messaging
        if "kafkajs" in all_deps or "confluent-kafka" in all_deps:
            self._add_technology(TechDetection("Kafka", path, "Kafka dependency found"))
        if "amqplib" in all_deps or "rabbitmq" in all_deps:
            self._add_technology(TechDetection("RabbitMQ", path, "RabbitMQ dependency found"))
        if "nats" in all_deps:
            self._add_technology(TechDetection("NATS", path, "NATS dependency found"))

        # Monitoring
        if "prometheus-client" in all_deps or "prometheus-api" in all_deps:
            self._add_technology(TechDetection("Prometheus", path, "Prometheus dependency found"))
        if "grafana" in all_deps:
            self._add_technology(TechDetection("Grafana", path, "Grafana dependency found"))
        if any(k for k in all_deps if "opentelemetry" in k):
            self._add_technology(TechDetection("OpenTelemetry", path, "OpenTelemetry dependency found"))
        if "datadog" in all_deps or "@datadog/datadog-api-client" in all_deps:
            self._add_technology(TechDetection("Datadog", path, "Datadog dependency found"))
        if "newrelic" in all_deps:
            self._add_technology(TechDetection("New Relic", path, "New Relic dependency found"))

        # Testing
        if "jest" in all_deps:
            self._add_technology(TechDetection("Jest", path, "jest dependency found"))
        if "vitest" in all_deps:
            self._add_technology(TechDetection("Vitest", path, "vitest dependency found"))
        if "mocha" in all_deps:
            self._add_technology(TechDetection("Mocha", path, "mocha dependency found"))
        if "cypress" in all_deps:
            self._add_technology(TechDetection("Cypress", path, "cypress dependency found"))
        if "@playwright/test" in all_deps:
            self._add_technology(TechDetection("Playwright", path, "Playwright dependency found"))

        # Linting/Formatting
        if "eslint" in all_deps:
            self._add_technology(TechDetection("ESLint", path, "eslint dependency found"))
        if "prettier" in all_deps:
            self._add_technology(TechDetection("Prettier", path, "prettier dependency found"))

        # Auth
        if "jsonwebtoken" in all_deps or "jwt" in all_deps:
            self._add_technology(TechDetection("JWT", path, "JWT dependency found"))
        if "passport" in all_deps:
            self._add_technology(TechDetection("Passport", path, "Passport dependency found"))
        if "@auth0" in str(all_deps):
            self._add_technology(TechDetection("Auth0", path, "Auth0 dependency found"))
        if "@keycloak/keycloak-admin-client" in all_deps:
            self._add_technology(TechDetection("Keycloak", path, "Keycloak dependency found"))
        if "@clerk/clerk-sdk-node" in all_deps:
            self._add_technology(TechDetection("Clerk", path, "Clerk dependency found"))
        if "next-auth" in all_deps or "@auth/core" in all_deps:
            self._add_technology(TechDetection("NextAuth", path, "NextAuth dependency found"))

        # AI/ML
        if "openai" in all_deps:
            self._add_technology(TechDetection("OpenAI", path, "openai dependency found"))
        if "langchain" in all_deps or "@langchain/core" in all_deps:
            self._add_technology(TechDetection("LangChain", path, "LangChain dependency found"))
        if "llama-index" in all_deps:
            self._add_technology(TechDetection("LlamaIndex", path, "llama-index dependency found"))
        if "@google/generative-ai" in all_deps:
            self._add_technology(TechDetection("Google GenAI", path, "Google GenAI dependency found"))
        if "transformers" in all_deps:
            self._add_technology(TechDetection("Transformers", path, "Transformers dependency found"))
        if "tensorflow" in all_deps or "tfjs" in all_deps:
            self._add_technology(TechDetection("TensorFlow", path, "TensorFlow dependency found"))
        if "torch" in all_deps or "pytorch" in all_deps:
            self._add_technology(TechDetection("PyTorch", path, "PyTorch dependency found"))

    def _detect_from_requirements_txt(self, path: str, requirements: List[str]):
        reqs_lower = [str(r).lower() for r in requirements]

        if "fastapi" in reqs_lower or "uvicorn" in reqs_lower:
            self._add_technology(TechDetection("FastAPI", path, "fastapi/uvicorn dependency found"))
        if "django" in reqs_lower or "djangorestframework" in reqs_lower:
            self._add_technology(TechDetection("Django", path, "django/djangorestframework dependency found"))
        if "flask" in reqs_lower:
            self._add_technology(TechDetection("Flask", path, "flask dependency found"))

        if "sqlalchemy" in reqs_lower:
            self._add_technology(TechDetection("SQLAlchemy", path, "sqlalchemy dependency found"))
        if "psycopg2" in reqs_lower or "psycopg" in reqs_lower or "postgresql" in reqs_lower:
            self._add_technology(TechDetection("PostgreSQL", path, "psycopg/postgresql dependency found"))
        if "mysql" in reqs_lower or "mysqlclient" in reqs_lower or "mysql-connector" in reqs_lower:
            self._add_technology(TechDetection("MySQL", path, "mysql dependency found"))
        if "pymongo" in reqs_lower or "mongoengine" in reqs_lower or "mongodb" in reqs_lower:
            self._add_technology(TechDetection("MongoDB", path, "mongo dependency found"))
        if "redis" in reqs_lower or "redis-py" in reqs_lower:
            self._add_technology(TechDetection("Redis", path, "redis dependency found"))
        if "sqlite" in reqs_lower:
            self._add_technology(TechDetection("SQLite", path, "sqlite dependency found"))
        if "mariadb" in reqs_lower:
            self._add_technology(TechDetection("MariaDB", path, "mariadb dependency found"))
        if "elasticsearch" in reqs_lower:
            self._add_technology(TechDetection("Elasticsearch", path, "Elasticsearch dependency found"))

        if "boto3" in reqs_lower or "botocore" in reqs_lower:
            self._add_technology(TechDetection("AWS", path, "boto3/botocore dependency found"))
        if any(r for r in reqs_lower if "azure" in r):
            self._add_technology(TechDetection("Azure", path, "Azure SDK dependency found"))
        if any(r for r in reqs_lower if "google-cloud" in r):
            self._add_technology(TechDetection("GCP", path, "Google Cloud SDK dependency found"))

        if "kafka-python" in reqs_lower or "confluent-kafka" in reqs_lower:
            self._add_technology(TechDetection("Kafka", path, "Kafka dependency found"))
        if "pika" in reqs_lower or "rabbitmq" in reqs_lower:
            self._add_technology(TechDetection("RabbitMQ", path, "RabbitMQ dependency found"))
        if "nats" in reqs_lower:
            self._add_technology(TechDetection("NATS", path, "NATS dependency found"))

        if "prometheus-client" in reqs_lower:
            self._add_technology(TechDetection("Prometheus", path, "prometheus-client dependency found"))
        if any(r for r in reqs_lower if "opentelemetry" in r):
            self._add_technology(TechDetection("OpenTelemetry", path, "OpenTelemetry dependency found"))
        if "datadog" in reqs_lower:
            self._add_technology(TechDetection("Datadog", path, "Datadog dependency found"))
        if "newrelic" in reqs_lower:
            self._add_technology(TechDetection("New Relic", path, "New Relic dependency found"))

        if "pytest" in reqs_lower:
            self._add_technology(TechDetection("Pytest", path, "pytest dependency found"))
        if "black" in reqs_lower:
            self._add_technology(TechDetection("Black", path, "black dependency found"))
        if "ruff" in reqs_lower:
            self._add_technology(TechDetection("Ruff", path, "ruff dependency found"))
        if "mypy" in reqs_lower:
            self._add_technology(TechDetection("MyPy", path, "mypy dependency found"))
        if "poetry" in reqs_lower:
            self._add_technology(TechDetection("Poetry", path, "poetry dependency found"))

        if "openai" in reqs_lower:
            self._add_technology(TechDetection("OpenAI", path, "openai dependency found"))
        if "langchain" in reqs_lower:
            self._add_technology(TechDetection("LangChain", path, "langchain dependency found"))
        if "llama-index" in reqs_lower:
            self._add_technology(TechDetection("LlamaIndex", path, "llama-index dependency found"))
        if "transformers" in reqs_lower:
            self._add_technology(TechDetection("Transformers", path, "transformers dependency found"))
        if "tensorflow" in reqs_lower:
            self._add_technology(TechDetection("TensorFlow", path, "tensorflow dependency found"))
        if "torch" in reqs_lower:
            self._add_technology(TechDetection("PyTorch", path, "torch/pytorch dependency found"))

    def _has_tf_resource(self, content: str, resource_prefix: str) -> bool:
        escaped_prefix = re.escape(resource_prefix)
        return bool(re.search(rf'\b(resource|data)\s+"{escaped_prefix}', content))

    def _stage3_categorize_and_aggregate(self) -> Dict[str, List[Dict]]:
        """Categorize technologies and aggregate duplicates"""
        # Define category mappings
        frontend_techs = {"React", "Next.js", "Vue", "Nuxt", "Angular", "Svelte", "SolidJS", "Astro", "Remix", "Qwik", "Material UI"}
        backend_techs = {
            "Express", "NestJS", "FastAPI", "Flask", "Django", "Spring Boot", "Laravel",
            "Gin", "Fiber", "Echo", "Rails", "Phoenix", "ASP.NET"
        }
        database_techs = {
            "PostgreSQL", "MySQL", "MariaDB", "MongoDB", "Redis", "SQLite", "Elasticsearch",
            "OpenSearch", "Cassandra", "DynamoDB", "Prisma", "TypeORM", "Sequelize", "Drizzle",
            "SQLAlchemy", "Hibernate", "Mongoose", "GORM", "Entity Framework", "Memcached",
            "Meilisearch", "Algolia", "RDS"
        }
        infrastructure_techs = {
            "Terraform", "CloudFormation", "Pulumi"
        }
        devops_techs = {
            "Docker", "Podman", "Kubernetes", "Helm", "Kustomize", "GitHub Actions",
            "GitLab CI", "Jenkins", "CircleCI", "ArgoCD", "Argo Workflows"
        }
        cloud_techs = {
            "AWS", "Azure", "GCP", "Cloudflare", "Firebase", "Lambda", "S3",
            "EKS", "ECS", "Cloud Run", "GKE", "AKS", "API Gateway", "Cognito",
            "CloudWatch"
        }
        monitoring_techs = {
            "Prometheus", "Grafana", "Datadog", "New Relic", "OpenTelemetry"
        }
        messaging_techs = {
            "Kafka", "RabbitMQ", "NATS", "SQS", "SNS"
        }
        tooling_techs = {
            "Vite", "Webpack", "Rollup", "Parcel", "TurboPack", "Maven", "Gradle",
            "npm", "Yarn", "pnpm", "bun", "Poetry", "Cargo", "TailwindCSS", "Material UI", "Redux",
            "Zustand", "React Query", "JWT", "Passport", "Auth0", "Keycloak", "Clerk",
            "NextAuth", "Jest", "Vitest", "Mocha", "Pytest", "JUnit", "Cypress",
            "Playwright", "ESLint", "Prettier", "Black", "Ruff", "MyPy", "FFmpeg",
            "ImageMagick", "OpenAI", "LangChain", "LlamaIndex", "Google GenAI",
            "Transformers", "TensorFlow", "PyTorch"
        }

        # Aggregate technologies by name
        tech_aggregation: Dict[str, Dict[str, Any]] = {}
        
        for tech in self.technologies:
            if tech.name not in tech_aggregation:
                tech_aggregation[tech.name] = {
                    "name": tech.name,
                    "count": 0,
                    "sources": [],
                    "evidence": []
                }
            
            if tech.source not in tech_aggregation[tech.name]["sources"]:
                tech_aggregation[tech.name]["sources"].append(tech.source)
                tech_aggregation[tech.name]["count"] += 1
            if tech.evidence not in tech_aggregation[tech.name]["evidence"]:
                tech_aggregation[tech.name]["evidence"].append(tech.evidence)

        # Categorize aggregated technologies
        categories = {
            "frontend": [],
            "backend": [],
            "database": [],
            "infrastructure": [],
            "devops": [],
            "cloud": [],
            "monitoring": [],
            "messaging": [],
            "tooling": []
        }

        for tech_name, tech_data in tech_aggregation.items():
            if tech_name in frontend_techs:
                categories["frontend"].append(tech_data)
            elif tech_name in backend_techs:
                categories["backend"].append(tech_data)
            elif tech_name in database_techs:
                categories["database"].append(tech_data)
            elif tech_name in infrastructure_techs:
                categories["infrastructure"].append(tech_data)
            elif tech_name in devops_techs:
                categories["devops"].append(tech_data)
            elif tech_name in cloud_techs:
                categories["cloud"].append(tech_data)
            elif tech_name in monitoring_techs:
                categories["monitoring"].append(tech_data)
            elif tech_name in messaging_techs:
                categories["messaging"].append(tech_data)
            elif tech_name in tooling_techs:
                categories["tooling"].append(tech_data)

        return categories
