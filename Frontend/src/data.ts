import { Repository, FileTreeNode, SimilarRepo } from './types';

// Concrete presets for premium demonstration in the UI
export const PRESETS: Record<string, Repository> = {
  "vercel/next.js": {
    owner: "vercel",
    name: "next.js",
    fullName: "vercel/next.js",
    description: "The React Framework for the Web. Used by some of the world's largest companies, Next.js enables you to create high-performance web applications.",
    stars: 122409,
    forks: 26182,
    language: "TypeScript",
    topics: ["react", "nextjs", "framework", "web-development", "ssr", "typescript", "serverless", "isr"],
    url: "https://github.com/vercel/next.js",
    overview: {
      aiSummary: "Next.js is a zero-configuration React framework that provides automatic system-level optimizations like server-side rendering (SSR), static site generation (SSG), and incremental static regeneration (ISR). By providing standard file-system routing, out-of-the-box support for Tailwind CSS, internationalization, and optimized image rendering, it acts as the foundation for modern enterprise web frontends.",
      info: {
        license: "MIT",
        contributors: 3120,
        openIssues: 1845,
        lastCommit: "2 minutes ago"
      },
      stats: {
        linesOfCode: "1.4M",
        filesCount: 14820,
        commitsCount: "31,894",
        pullRequests: 1450
      },
      topics: ["React", "Framework", "Vercel", "Server-Side Rendering", "Rust Compiler", "SWC", "Turbopack"]
    },
    analysis: {
      projectSummary: "Next.js integrates a dual-engine architecture: a Node.js-based server-side runtime for managing rendering, dynamic API endpoints, and edge middleware; coupled with Turbopack (a Rust-based bundler) for blazing-fast local compilation. It separates static asset generation from dynamic runtime queries, routing visitor traffic through optimized global edge CDNs.",
      techStack: {
        frontend: ["React 19", "Tailwind CSS", "MTS Routing", "WebVitals API"],
        backend: ["Node.js Edge Runtime", "TypeScript Compiler", "Next Server Engine"],
        database: ["PostgreSQL (Compatible)", "Redis (Edge Cache caching)"],
        infrastructure: ["Vercel Edge Network", "AWS Lambda", "Cloudflare Workers (Edge Nodes)"],
        devops: ["GitHub Actions", "Turborepo", "Turbopack", "ESLint", "Prettier"]
      },
      keyFeatures: [
        "**App Router Support**: Utilizes React Server Components, loading states, error boundaries, and nested layouts.",
        "**Optimized Asset Loading**: Integrated next/image, next/font, and next/script elements with automatic placeholder injection.",
        "**Rust-based SWC Compiler**: Superb local compilation times replacing legacy Babel processing.",
        "**Edge Middleware Engine**: Run fast cookies, redirects, and geo-ip routing rules directly at the CDN tier."
      ]
    },
    folderStructure: [
      {
        name: "packages",
        type: "folder",
        children: [
          {
            name: "next",
            type: "folder",
            children: [
              { name: "src", type: "folder", children: [
                { name: "client", type: "folder", children: [{ name: "index.ts", type: "file", size: "12 KB" }] },
                { name: "server", type: "folder", children: [{ name: "next-server.ts", type: "file", size: "45 KB" }] }
              ]},
              { name: "package.json", type: "file", size: "4 KB" }
            ]
          },
          { name: "next-swc", type: "folder" },
          { name: "turbopack", type: "folder" }
        ]
      },
      { name: "errors", type: "folder" },
      { name: "examples", type: "folder" },
      { name: "test", type: "folder" },
      { name: "package.json", type: "file", size: "8 KB" },
      { name: "turbo.json", type: "file", size: "1.2 KB" }
    ],
    similarRepos: [
      {
        fullName: "remix-run/remix",
        description: "Build Better Websites. Remix is a full-stack web framework that lets you focus on user interface and work back through web standards.",
        stars: 27150,
        forks: 2311,
        language: "TypeScript",
        topics: ["remix", "react", "framework", "ssr"]
      },
      {
        fullName: "facebook/react",
        description: "The library for web and native user interfaces.",
        stars: 224012,
        forks: 46210,
        language: "JavaScript",
        topics: ["react", "library", "ui", "frontend"]
      },
      {
        fullName: "nuxt/nuxt",
        description: "The Intuitive Vue Framework. Build your next Vue.js application with confidence.",
        stars: 52912,
        forks: 4850,
        language: "TypeScript",
        topics: ["vue", "framework", "ssr", "nuxt"]
      }
    ]
  },

  "supabase/supabase": {
    owner: "supabase",
    name: "supabase",
    fullName: "supabase/supabase",
    description: "The open source Firebase alternative. Supabase provides all the backend features you need to build a product: database, auth, storage, and edge functions.",
    stars: 71290,
    forks: 5812,
    language: "TypeScript",
    topics: ["firebase-alternative", "postgresql", "rest-api", "auth", "realtime", "typescript", "go"],
    url: "https://github.com/supabase/supabase",
    overview: {
      aiSummary: "Supabase compiles a suite of independent, open-source utilities into a seamless cloud backend, centering heavily on PostgreSQL. It automatically auto-generates RESTful and GraphQL APIs from your database schemas, handles secure Go/Node Auth, manages distributed S3 uploads, and broadcasts real-time Postgres CDC events via WebSockets.",
      info: {
        license: "Apache-2.0",
        contributors: 940,
        openIssues: 540,
        lastCommit: "10 minutes ago"
      },
      stats: {
        linesOfCode: "820K",
        filesCount: 6810,
        commitsCount: "14,834",
        pullRequests: 320
      },
      topics: ["Firebase", "PostgreSQL", "Authentication", "Edge Functions", "Realtime WebSockets", "S3 Storage"]
    },
    analysis: {
      projectSummary: "Supabase runs a PostgreSQL engine wrapped by PostgREST to automatically expose secure RESTful APIs. Authentication is run via GoTrue, storage requests move through custom S3 middleware files, and database mutations are broadcast across Phoenix/Elixir channels to client frontend listeners.",
      techStack: {
        frontend: ["React", "TypeScript", "Tailwind CSS", "NextJS (Dashboards)"],
        backend: ["PostgREST (HASKELL)", "GoTrue (Go)", "Realtime (Elixir)", "Edge Runtime (Deno)"],
        database: ["PostgreSQL", "pgvector", "Redis"],
        infrastructure: ["AWS ECS", "DigitalOcean Clusters", "Cloudflare Tunnel Services"],
        devops: ["Docker Compose", "GitHub Actions", "Pulumi Terraform"]
      },
      keyFeatures: [
        "**Realtime CDC Engine**: Listens to PostgreSQL WAL logs and safely broadcasts server mutations to active client listeners.",
        "**Row Level Security (RLS)**: Integrates directly with Postgres SQL policies, marrying data authentication right into the database layer.",
        "**Deno-powered Edge Functions**: Execute zero-latency TypeScript functions globally with minimal cold starts.",
        "**Auto-Generated APIs**: Instantly creates GraphQL, REST, and type-safe SDK interfaces based on the underlying relational tables."
      ]
    },
    folderStructure: [
      {
        name: "apps",
        type: "folder",
        children: [
          { name: "studio", type: "folder", children: [{ name: "package.json", type: "file", size: "3 KB" }] },
          { name: "docs", type: "folder" }
        ]
      },
      {
        name: "packages",
        type: "folder",
        children: [
          { name: "supabase-js", type: "folder" },
          { name: "realtime-js", type: "folder" }
        ]
      },
      { name: "docker", type: "folder", children: [{ name: "docker-compose.yml", type: "file", size: "12 KB" }] },
      { name: "web", type: "folder" }
    ],
    similarRepos: [
      {
        fullName: "pocketbase/pocketbase",
        description: "Open source Go backend for your next SaaS and Mobile app in 1 file.",
        stars: 38400,
        forks: 1890,
        language: "Go",
        topics: ["go", "sqlite", "backend-as-a-service"]
      },
      {
        fullName: "appwrite/appwrite",
        description: "Secure open-source backend for Web, Mobile & Flutter developers, packaged as Docker containers.",
        stars: 44200,
        forks: 3950,
        language: "TypeScript",
        topics: ["baas", "docker", "auth", "storage"]
      }
    ]
  },

  "kubernetes/kubernetes": {
    owner: "kubernetes",
    name: "kubernetes",
    fullName: "kubernetes/kubernetes",
    description: "Production-Grade Container Scheduling and Orchestration. Kubernetes automates deploying, scaling, and managing containerized applications globally.",
    stars: 109240,
    forks: 39820,
    language: "Go",
    topics: ["kubernetes", "containers", "orchestration", "go", "cloud-native", "docker", "microservices"],
    url: "https://github.com/kubernetes/kubernetes",
    overview: {
      aiSummary: "Kubernetes is the gold standard of container orchestration. Written in Go, it features a highly resilient control loop architecture that matches cluster deployments to a desired state configuration, automating multi-node scheduling, secure ingress balancing, service discoverability, and rolling zero-downtime updates.",
      info: {
        license: "Apache-2.0",
        contributors: 4200,
        openIssues: 3200,
        lastCommit: "5 seconds ago"
      },
      stats: {
        linesOfCode: "5.8M",
        filesCount: 42100,
        commitsCount: "115,402",
        pullRequests: 3250
      },
      topics: ["DevOps", "Cloud Native", "Container Orchestration", "CRI", "CNI", "etcd Cluster State", "Control Loops"]
    },
    analysis: {
      projectSummary: "Kubernetes utilizes a server-agent cluster framework. The Master Control Plane acts as the main entry point via `kube-apiserver`, persisting configurations in highly available `etcd` key-value keyrings. Minion Worker Nodes pull instructions, managing container workloads on individual hosts through the local `kubelet` agent.",
      techStack: {
        frontend: ["Kubernetes Dashboard (React/TypeScript)", "Lens IDE"],
        backend: ["Go (Golang Systems Engine)", "C++ Core Extensions"],
        database: ["etcd (High-performance Raft consensus state)"],
        infrastructure: ["Bare Metal Servers", "AWS EKS", "Google GKE", "Azure AKS"],
        devops: ["Kustomize", "Helm charts", "Bazel (Historical)", "GitHub Enterprise workflows"]
      },
      keyFeatures: [
        "**Self-healing Workloads**: Auto-restarts failed containers, spins up replicas when nodes sleep, and drops unhealthy endpoints.",
        "**Horizontal Autoscaling**: Dynamically increases or reduces replica allocations based on CPU limits, custom metrics, or HTTP queries.",
        "**Service Mesh Networking**: Integrates container IPs natively with local load balancers to route external ingress directly to target app nodes.",
        "**Distributed Secret Control**: Injects API keys, credentials, and configuration files securely into pods without changing base images."
      ]
    },
    folderStructure: [
      {
        name: "api",
        type: "folder",
        children: [
          { name: "openapi", type: "folder" },
          { name: "core", type: "folder" }
        ]
      },
      {
        name: "pkg",
        type: "folder",
        children: [
          { name: "kubelet", type: "folder", children: [{ name: "kubelet.go", type: "file", size: "120 KB" }] },
          { name: "scheduler", type: "folder" },
          { name: "proxy", type: "folder" }
        ]
      },
      { name: "cmd", type: "folder", children: [{ name: "kube-apiserver", type: "folder" }] },
      { name: "test", type: "folder" }
    ],
    similarRepos: [
      {
        fullName: "docker/cli",
        description: "The official command line tool for Docker. Simple single-node orchestration and container commands.",
        stars: 34100,
        forks: 6900,
        language: "Go",
        topics: ["docker", "cmd", "containers", "go"]
      },
      {
        fullName: "hashicorp/nomad",
        description: "Nomad is an easy-to-use, flexible, and enterprise-grade workload orchestrator to deploy and manage containers and non-containerized applications.",
        stars: 16100,
        forks: 1800,
        language: "Go",
        topics: ["nomad", "hashicorp", "scheduler", "orchestration"]
      }
    ]
  },

  "typescript": {
    owner: "microsoft",
    name: "TypeScript",
    fullName: "microsoft/TypeScript",
    description: "TypeScript is a superset of JavaScript that compiles to clean JavaScript output, adding static typing annotations to prevent crashes.",
    stars: 101230,
    forks: 13900,
    language: "TypeScript",
    topics: ["typescript", "javascript", "compiler", "type-checker", "microsoft", "ecmascript"],
    url: "https://github.com/microsoft/TypeScript",
    overview: {
      aiSummary: "TypeScript is a powerful compile-to-JS structural language. Developed by Microsoft, it introduces robust type checking, static annotations, strict namespaces, interfaces, and decorators that resolve syntax issues at development time rather than in browser runtime crashes.",
      info: {
        license: "Apache-2.0",
        contributors: 810,
        openIssues: 5600,
        lastCommit: "1 hour ago"
      },
      stats: {
        linesOfCode: "2.1M",
        filesCount: 16200,
        commitsCount: "42,910",
        pullRequests: 820
      },
      topics: ["Microsoft", "Language Compiler", "Static Typing", "JavaScript Runtime", "ESLint Parsing"]
    },
    analysis: {
      projectSummary: "The TypeScript implementation center is a scanning, parsing, binder, checker, and code emitter engine. Written entirely in TypeScript, it ingests source strings, builds an Abstract Syntax Tree (AST), validates symbols, and transpiles clean JavaScript output matching configurable ECMAScript targets.",
      techStack: {
        frontend: ["Playground IDE (React / Web Components)"],
        backend: ["tsc (NodeJS CLI binary wrapper)"],
        database: ["Local State Cache Engine"],
        infrastructure: ["Node.js execution sandbox"],
        devops: ["GitHub Actions Scripts", "Lerna Mono Repo", "ESLint Core Plugins"]
      },
      keyFeatures: [
        "**Abstract Syntax Parsing (AST)**: Builds strict syntax trees mapping full symbol declarations to dynamic usage nodes.",
        "**Robust Type Interference**: Evaluates complex generics, intersections, dynamic union constraints, and map shapes.",
        "**Visual Studio Language Service**: Delivers superfast autocomplete, real-time code diagnostics, and code-lens indicators.",
        "**Configurable Build Target**: Emits JavaScript targeting anything from legacy ES5 environments up to modern ESNext runtimes."
      ]
    },
    folderStructure: [
      {
        name: "src",
        type: "folder",
        children: [
          { name: "compiler", type: "folder", children: [
            { name: "checker.ts", type: "file", size: "2.4 MB" },
            { name: "parser.ts", type: "file", size: "480 KB" },
            { name: "binder.ts", type: "file", size: "210 KB" },
            { name: "emitter.ts", type: "file", size: "320 KB" }
          ]},
          { name: "services", type: "folder" },
          { name: "harness", type: "folder" }
        ]
      },
      { name: "tests", type: "folder" },
      { name: "package.json", type: "file", size: "5 KB" }
    ],
    similarRepos: [
      {
        fullName: "swc-project/swc",
        description: "SWC is an ultra-fast Rust-based compilation engine designed for JavaScript and TypeScript parsing.",
        stars: 29400,
        forks: 1400,
        language: "Rust",
        topics: ["rust", "compiler", "swc", "typescript"]
      }
    ]
  }
};

// Generates high-fidelity repository intelligence dynamically for any search query or pasted URL!
export function getOrCreateRepository(input: string): Repository {
  const cleanInput = input.trim().toLowerCase().replace("https://github.com/", "");
  
  // Look for exact matches in our extensive preset list
  const presetKey = Object.keys(PRESETS).find(key => 
    key === cleanInput || 
    cleanInput.includes(key) || 
    key.split("/")[1] === cleanInput
  );
  
  if (presetKey) {
    return PRESETS[presetKey];
  }

  // Define components from input
  let owner = "repoiq-scanner";
  let name = cleanInput.replace(/\s+/g, "-") || "analyzed-sandbox";
  
  if (cleanInput.includes("/")) {
    const parts = cleanInput.split("/");
    owner = parts[0] || "custom";
    name = parts[1] || "repository";
  }

  const capitalizedName = name.split("-").map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
  const capitalizedOwner = owner.charAt(0).toUpperCase() + owner.slice(1);
  const fullName = `${owner}/${name}`;

  // Analyze keyword matching to tailor topics and stack dynamically
  let topicMatches: string[] = ["github", "developer-tools", "ai-engine"];
  let frontendMods: string[] = ["React", "TypeScript", "Tailwind CSS"];
  let backendMods: string[] = ["Node.js Express", "FastAPI (Python)"];
  let databaseMods: string[] = ["PostgreSQL Engine", "Redis Cache"];
  let infraMods: string[] = ["Vercel CDN Network", "AWS ECS Clusters"];
  let devopsMods: string[] = ["GitHub Actions Workspace", "Docker Environment"];
  let archDescription = "Standard modern cloud-native system featuring a high-concurrency client browser interface connecting synchronously to load-balanced backend APIs, storing durable states in state-management layers.";

  if (cleanInput.includes("file") || cleanInput.includes("share") || cleanInput.includes("storage")) {
    topicMatches = ["file-sharing", "cloud-storage", "encrypted", "s3-uploads", "nextcloud"];
    frontendMods = ["React 19 Hooks", "Tailwind CSS Fluid", "Uppy File Uploader"];
    backendMods = ["Go Fiber API Router", "Node Stream Handler"];
    databaseMods = ["PostgreSQL Relational", "Redis Session Cluster"];
    infraMods = ["AWS S3 Distributed Bucket", "Cloudflare CDN Edge Assets"];
    devopsMods = ["Docker Compose Deployments", "Vercel Build Hooks"];
    archDescription = "The application processes binary multi-part file uploads directly from client browsers through secure Cloudflare tunnels into isolated Node streaming pipelines before storing files in AWS S3 with PostgreSQL handling access metadata.";
  } else if (cleanInput.includes("bot") || cleanInput.includes("ai") || cleanInput.includes("chat") || cleanInput.includes("model")) {
    topicMatches = ["ai-chat", "llm-wrapper", "gemini-api", "vector-db", "prompt-engineering"];
    frontendMods = ["React Functional Components", "Tailwind Prose", "Audio Speech WebAPI"];
    backendMods = ["Express API Server", "Python FastAPI", "@google/genai SDK Integration"];
    databaseMods = ["pgvector Database", "Pinecone Cloud DB"];
    infraMods = ["Google Cloud Platform VM", "Vercel Serverless Functions"];
    devopsMods = ["GitHub CI/CD Automation", "Docker Core Engine", "Gemini Middleware Config"];
    archDescription = "Users pass prompt queries into a high-fidelity React frontend. The request is processed on the backend through a secure @google/genai SDK wrapper, utilizing pgvector storage to read/write context embedding states.";
  } else if (cleanInput.includes("kube") || cleanInput.includes("docker") || cleanInput.includes("ops") || cleanInput.includes("infra")) {
    topicMatches = ["devops", "cloud-orchestration", "kubernetes-dashboard", "helm", "yaml-compiler"];
    frontendMods = ["React Terminal Slate", "Recharts Visualizers", "WebSockets Logs"];
    backendMods = ["Go Prometheus Scraper", "Node Cluster Controller"];
    databaseMods = ["etcd Distributed Keyring", "InfluxDB TimeSeries"];
    infraMods = ["AWS EKS Node Groups", "Google Kubernetes Engine Nodes"];
    devopsMods = ["Terraform Infrastructure-as-code", "Docker Container Images", "Ansible Roles"];
    archDescription = "Exposed status logs are retrieved from target server hypervisors by Prometheus query aggregators. Stats are serialized and compiled to JSON, feeding a clean web frontend over active WebSocket pipelines.";
  } else if (cleanInput.includes("shop") || cleanInput.includes("commerce") || cleanInput.includes("store")) {
    topicMatches = ["e-commerce", "stripe-payments", "cart-system", "tailwind-ui", "checkout"];
    frontendMods = ["React Server Modules", "Tailwind UI Elements", "Framer Motion FX"];
    backendMods = ["Node Server Engine", "Stripe API SDK Proxy"];
    databaseMods = ["PostgreSQL Catalog", "Redis Session Cache"];
    infraMods = ["Vercel Edge Routes", "AWS Node Servers"];
    devopsMods = ["Sentry Error Diagnostics", "GitHub Deployment Hooks"];
    archDescription = "Secure payment processing routes checkout tokens natively using Stripe servers. App databases process secure transactions client-side, while product data is fetched instantly through Redis caching loops.";
  }

  // Create highly realistic mock stars, forks, issues, lines of code, etc.
  const hash = input.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const starsPrm = 1200 + (hash % 14500);
  const forksPrm = Math.floor(starsPrm * 0.23);
  const contributors = 15 + (hash % 120);
  const issues = 5 + (hash % 180);
  const codeLines = `${(100 + (hash % 900))}K`;
  const fileCount = 200 + (hash % 2000);
  
  return {
    owner,
    name,
    fullName,
    description: `AI-powered analyzed repository for "${capitalizedName}". Automatically detected full-stack architecture, folder layout summaries, similar active codebases, and custom operational diagrams.`,
    stars: starsPrm,
    forks: forksPrm,
    language: hash % 2 === 0 ? "TypeScript" : "Go",
    topics: topicMatches,
    url: input.startsWith("http") ? input : `https://github.com/${fullName}`,
    overview: {
      aiSummary: `The "${capitalizedName}" repository is a modern high-performance system designed for scale. Supported mainly by a ${hash % 2 === 0 ? "TypeScript" : "Go"} codebase, it builds upon a robust component hierarchy, delivering efficient execution, detailed logging, standard modular configurations, and comprehensive unit coverage.`,
      info: {
        license: hash % 3 === 0 ? "Apache-2.0" : "MIT",
        contributors,
        openIssues: issues,
        lastCommit: "12 minutes ago"
      },
      stats: {
        linesOfCode: codeLines,
        filesCount: fileCount,
        commitsCount: `${(324 + (hash % 8500))}`,
        pullRequests: 12 + (hash % 80)
      },
      topics: topicMatches.map(t => t.charAt(0).toUpperCase() + t.slice(1))
    },
    analysis: {
      projectSummary: archDescription,
      techStack: {
        frontend: frontendMods,
        backend: backendMods,
        database: databaseMods,
        infrastructure: infraMods,
        devops: devopsMods
      },
      keyFeatures: [
        `**High-performance Client Architecture**: Tailored components built with modern ${frontendMods[0]} and styled using robust utility classes.`,
        `**Scalable Core Engine**: Powerful backend services running ${backendMods[0]} to support high-throughput operations.`,
        `**Secure Data Pipelines**: Real-time schema support leveraging ${databaseMods[0]} with multi-node validation checks.`,
        `**Fully Orchestrated Infrastructure**: Scaled automatically across ${infraMods[0]} with continuous delivery updates.`
      ]
    },
    folderStructure: [
      {
        name: "src",
        type: "folder",
        children: [
          { name: "components", type: "folder", children: [
            { name: "dashboard.tsx", type: "file", size: "18 KB" },
            { name: "header.tsx", type: "file", size: "8 KB" }
          ]},
          { name: "lib", type: "folder", children: [
            { name: "utils.ts", type: "file", size: "4 KB" },
            { name: "db.ts", type: "file", size: "11 KB" }
          ]},
          { name: "styles", type: "folder" },
          { name: "app.ts", type: "file", size: "32 KB" }
        ]
      },
      { name: "public", type: "folder" },
      { name: "tests", type: "folder" },
      { name: "docker-compose.yml", type: "file", size: "2.4 KB" },
      { name: "package.json", type: "file", size: "3.2 KB" },
      { name: "README.md", type: "file", size: "5.1 KB" }
    ],
    similarRepos: [
      {
        fullName: `${owner}-forks/${name}-alt`,
        description: `Highly optimized configuration alternatives for ${capitalizedName} implementing modern structures.`,
        stars: Math.floor(starsPrm * 0.4),
        forks: Math.floor(forksPrm * 0.4),
        language: hash % 2 === 0 ? "TypeScript" : "Go",
        topics: topicMatches.slice(0, 3)
      },
      {
        fullName: `oss-solutions/${name}-helper`,
        description: `Developer tools and helper extensions built specifically to support core integrations in this environment.`,
        stars: Math.floor(starsPrm * 0.15),
        forks: Math.floor(forksPrm * 0.15),
        language: "JavaScript",
        topics: ["plugins", "extensions", "developer-tools"]
      }
    ]
  };
}
