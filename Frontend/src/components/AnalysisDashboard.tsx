import React, { useState } from 'react';
import {
  Star, GitFork, BookMarked, Terminal, Code, Database, Globe,
  Settings, ChevronRight, Share2, ExternalLink, Sparkles,
  AlertCircle, Layout, Server, ArrowRight, Clock, Cpu,
  Layers, Award, BookOpen, Zap, Folder, File, ChevronDown, HelpCircle, ShieldCheck
} from 'lucide-react';
import { Repository, FileTreeNode } from '../types';

interface AnalysisDashboardProps {
  repo: Repository;
  isSaved: boolean;
  onSaveToggle: (fullName: string) => void;
  onBackToSearch: () => void;
  onAnalyze: (repoUrl: string) => void;
  serverAvailable: boolean;
}

// Compact interface matching requested technical modules
interface EducationalMetadata {
  projectType: string;
  maintenanceScore: string;
  badges: string[];
  architectureNodes: { name: string; desc: string; icon: any }[];
  requestFlow: { step: string; label: string }[];
  coreComponents: { title: string; desc: string }[];
  techStackWhy: { category: string; tech: string; why: string }[];
  learningConcepts: string[];
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
  prerequisites: string[];
  roadmap: { phase: string; title: string }[];
  relatedIdeas: string[];
  similarReposDetail: { fullName: string; whatItDoes: string; whySimilar: string; techStack: string[]; difficulty: string }[];
  scalabilityStudy: {
    cachingStrategy: string;
    concurrencyMethod: string;
    bottleneckMitigation: string;
  };
  designDecisions: {
    monorepoAdvantages: string;
    separationOfConcerns: string;
    securityLayerDesign: string;
  };
}

// Non-Technical overview data structure
interface CoreModule {
  name: string;
  iconName: string;
  purpose: string;
  responsibility: string;
  difficultyLevel: 'Easy' | 'Medium' | 'Hard';
  keyFilesFolders: string[];
  dependencies: string[];
}

interface InteractionLink {
  from: string;
  to: string;
  flowDesc: string;
}

interface DependencyMap {
  description: string;
  interactions: InteractionLink[];
}

interface NonTechnicalOverview {
  projectName: string;
  analogy: string;
  whatItDoes: string;
  whoUsesIt: string[];
  whyItExists: string;
  problemSolved: string;
  solutionProvided: string;
  simpleFeatures: { title: string; desc: string }[];
  coreModules: CoreModule[];
  dependencyMap: DependencyMap;
}

// 1. Get Non-Technical overview data
function getNonTechnicalOverview(fullName: string): NonTechnicalOverview {
  const clean = fullName.toLowerCase();

  if (clean.includes("next.js") || clean.includes("nextjs")) {
    return {
      projectName: "Next.js",
      analogy: "Next.js is like a smart modern physical book printing company. Instead of giving a reader loose pages of draft paper and making them bind and organize the book paragraphs in their own hands (which is how standard web libraries load, causing sluggish delays), Next.js pre-compiles and ships completely ready, beautifully finished books in seconds the moment a user asks for them.",
      whatItDoes: "It helps bloggers, startups, and massive companies build ultra-fast, modern websites. It automatically takes care of all the complex plumbing—like how different pages tie together, how files shrink, and how information updates—so creators can focus solely on what they write and design.",
      whoUsesIt: ["Online Business Owners", "Publishers & Bloggers", "E-Commerce Web Shops", "Digital Design Agencies"],
      whyItExists: "Previously, building interactive websites required a painful compromise. Web pages were either very fast but completely static (like digital flyers), or highly dynamic but painfully sluggish to load, demanding the user's phone to download massive heaps of technical data back-and-forth.",
      problemSolved: "Frustrated customers leaving your page because it displays a blank loading screen, and losing Google Search ranking due to heavy, laggy networks.",
      solutionProvided: "Constructs and pre-bakes your web pages on ultra-fast cloud networks prior to delivery, so pages open on your screen instantly.",
      simpleFeatures: [
        { title: "Instant-Load Pages", desc: "Speeds up page delivery so visitors see valuable content right away, keeping them hooked." },
        { title: "Microscale Photo Shrinker", desc: "Automatically shrinks heavy professional images so they look gorgeous on mobile lines without dragging your data limits." },
        { title: "Natural Addresses Map", desc: "Piles all your subpages in automatic order like typical computer folders, with no manual programming required." }
      ],
      coreModules: [
        {
          name: "Frontend (Client UI Pages)",
          iconName: "layout",
          purpose: "Deals directly with what visitors see on screen, rendering buttons, menus, and images.",
          responsibility: "Coordinates animation routines and listens to typing or clicks, keeping user experience fluid and responsive.",
          difficultyLevel: "Easy",
          keyFilesFolders: ["src/app/page.tsx", "src/components/"],
          dependencies: ["React 19", "Tailwind CSS", "Motion"]
        },
        {
          name: "Smart Page Router",
          iconName: "globe",
          purpose: "Automatically routes visitors to different web pages like /shop or /blog based on folders.",
          responsibility: "Pre-fetches other subpages in the background so that clicking a link loads the next view instantly.",
          difficultyLevel: "Medium",
          keyFilesFolders: ["src/app/layout.tsx", "src/app/blog/[id]/"],
          dependencies: ["Next.js Navigation", "URL Parser API"]
        },
        {
          name: "API & Action Gateways",
          iconName: "server",
          purpose: "Processes inputs, talks to external web applications, and runs calculations on secure computers.",
          responsibility: "Validates form submissions and runs secure queries without exposing password keys to visitors.",
          difficultyLevel: "Medium",
          keyFilesFolders: ["src/app/api/", "middleware.ts"],
          dependencies: ["Node.js Run", "Vercel SDK"]
        },
        {
          name: "Asset & Image Optimizer",
          iconName: "cpu",
          purpose: "Paints web page elements at blazing speeds by shrinking bulky file uploads.",
          responsibility: "Re-sizes massive images for mobile networks and bundles layout logic during development builds.",
          difficultyLevel: "Hard",
          keyFilesFolders: ["next.config.js", "turbopack/"],
          dependencies: ["SWC Compiler", "PostCSS", "Sharp Image Library"]
        }
      ],
      dependencyMap: {
        description: "How Next.js layers work in harmony: Your visitors click things on the Frontend page, which lets the Page Router fetch compiled templates from the Asset Optimizer while sending private data queries to the API Action Gateway.",
        interactions: [
          { from: "Frontend (Client UI Pages)", to: "Smart Page Router", flowDesc: "Sends active address queries when links are clicked" },
          { from: "Smart Page Router", to: "Asset & Image Optimizer", flowDesc: "Requests lightning-fast, pre-baked layouts and tiny images" },
          { from: "Frontend (Client UI Pages)", to: "API & Action Gateways", flowDesc: "Sends private form entries securely to back-end endpoints" }
        ]
      }
    };
  }

  if (clean.includes("supabase")) {
    return {
      projectName: "Supabase",
      analogy: "Supabase is like renting premium workspace in a highly secure, state-of-the-art office skyscraper with pre-hired vaults, identity guards, mailrooms, and custom express elevators already fully staffed. Instead of trying to build safe deposit vaults, hire armed guards, and install security systems on your own (which takes thousands of hours and risks massive leaks), you simply sign a document and start bringing in folders.",
      whatItDoes: "It acts as a secure, fast cloud filing cabinet for your modern applications. It stores password databases, reads and writes text forms, hosts uploaded image pools, and updates user boards smoothly without risking user security.",
      whoUsesIt: ["App Designers & Founders", "Tech Entrepreneurs", "Mobile Application Creators", "Rapid Prototypers"],
      whyItExists: "Every computer app needs an database behind it to store client passwords, profiles, and receipts. Setting up separate secure networks, password lockers, and continuous backups has historically been a lengthy and extremely error-prone task.",
      problemSolved: "Hiring expensive experts and spending weeks writing complex server checks just to let a user securely log in or back up pictures.",
      solutionProvided: "Exposes a pre-made secure vault package. It secures authentication and saves data instantly, letting you deploy a secure backend with a few simple steps.",
      simpleFeatures: [
        { title: "Secure Passkey Locksmith", desc: "Allows readers to safely sign up and log in using simple passwords or Google icons without writing custom verification algorithms." },
        { title: "Instant File Closets", desc: "A robust digital folder database letting users upload avatars, payment receipts, and multimedia files securely." },
        { title: "Live Screen Senders", desc: "Pushes real-time updates directly to everyone's screens instantly, perfect for chat channels and dynamic charts." }
      ],
      coreModules: [
        {
          name: "Authentication Security Desk",
          iconName: "shield",
          purpose: "Welcomes visitors, registers usernames, and lets users change password settings securely.",
          responsibility: "Creates encrypted web passes so browsers can prove identity on every single page handshake.",
          difficultyLevel: "Medium",
          keyFilesFolders: ["gotrue/", "src/lib/auth/"],
          dependencies: ["JSON Web Tokens", "GoTrue-js Client", "Crypto Engine"]
        },
        {
          name: "Relational Database Lockbox",
          iconName: "database",
          purpose: "Stores records in clear tables and filters who can view what using strict security check rules.",
          responsibility: "Ensures users can ONLY view their personal profile rows, locking out accidental eavesdroppers.",
          difficultyLevel: "Hard",
          keyFilesFolders: ["supabase/migrations/", "schema.sql"],
          dependencies: ["PostgreSQL Suite", "Row-Level Security (RLS)", "pgBouncer"]
        },
        {
          name: "Live Broadcast Dispatcher",
          iconName: "zap",
          purpose: "Sends database changes to other visitors' dashboards in the blink of an eye.",
          responsibility: "Creates continuous data pipelines so multiplayer game coordinates or chat rooms stream seamlessly.",
          difficultyLevel: "Medium",
          keyFilesFolders: ["realtime-engine/", "src/lib/realtime/"],
          dependencies: ["Elixir Phoenix", "WebSockets Engine"]
        },
        {
          name: "Asset Storage Closets",
          iconName: "folder",
          purpose: "Stores media attachments like user avatar graphics, PDF transcripts, and video items.",
          responsibility: "Checks database permission rules first before allowing any guest to open private paperwork.",
          difficultyLevel: "Easy",
          keyFilesFolders: ["storage/", "src/lib/storage/"],
          dependencies: ["Amazon S3 API", "Multer Service"]
        }
      ],
      dependencyMap: {
        description: "How Supabase modules interconnect: The Auth Security Desk verifies a visitor's passkey. Then, the client browser accesses files in the Database Lockbox (which double-checks Row Security) or uploads media directly to the Storage Closets, while any edits trigger the Live Dispatcher to sync other users' screens.",
        interactions: [
          { from: "Authentication Security Desk", to: "Relational Database Lockbox", flowDesc: "Provides dynamic identity credentials for row verification rules" },
          { from: "Relational Database Lockbox", to: "Live Broadcast Dispatcher", flowDesc: "Triggers instant alerts when entries are created, updated, or deleted" },
          { from: "Relational Database Lockbox", to: "Asset Storage Closets", flowDesc: "Verifies whether a guest has permissions to access files in specific buckets" }
        ]
      }
    };
  }

  if (clean.includes("kubernetes")) {
    return {
      projectName: "Kubernetes",
      analogy: "Kubernetes is like a master shipping port manager supervising a fleet of thousands of autonomous cargo boats. Since boats will occasionally break down, sink, or hit rough weather, the port manager monitors every ship in real-time. If a container vessel stops responding, he instantly deploys an identical cargo ship loaded with the exact duplicate inventory to take its place, meaning the port's deliveries are never interrupted.",
      whatItDoes: "It automatically monitors, restarts, and organizes hundreds of digital computer servers running your software. It ensures that even if half of your cloud computers lose power, your application stays completely operational without any human emergency calls.",
      whoUsesIt: ["Enterprise Platforms", "Cloud Operations Teams", "Software Service Networks", "Systems Administrators"],
      whyItExists: "As digital applications grow to support millions of concurrent users, they cannot run on a single machine. Managing hundreds of remote computers manually is manual chaos, leading to accidental outages and server bottlenecks.",
      problemSolved: "System operators being woken up by emergency alerts at 3 AM to manually restart crashed computers or configure networking lines.",
      solutionProvided: "A persistent cloud conductor where you simply specify how many copies of your app you want active. The conductor takes care of the scheduling, monitoring, and repairs automatically.",
      simpleFeatures: [
        { title: "Auto-healing Engine", desc: "Scours your server racks and immediately restarts any crashed app nodes inside fractions of a second." },
        { title: "Dynamic Scale Adaptor", desc: "Spawns additional server instances automatically during peak holiday sale rushes, and turns them off to save cash once users leave." },
        { title: "Rolling Server Upgrades", desc: "Upgrades your app to new versions one container at a time, ensuring zero disruption or downtime for active clients." }
      ],
      coreModules: [
        {
          name: "Central Command Controller",
          iconName: "terminal",
          purpose: "Directs everything, maintaining real-time checks to ensure your application servers are healthy.",
          responsibility: "Coordinates running allocations, monitors crashed machines, and instructs sub-managers to deploy replacements.",
          difficultyLevel: "Hard",
          keyFilesFolders: ["cmd/kube-apiserver/", "manifests/"],
          dependencies: ["Etcd Datastore", "gRPC Protocol"]
        },
        {
          name: "Worker Pod Deployers",
          iconName: "layers",
          purpose: "Acts as physical task executors, booting up cargo app units on actual server computers.",
          responsibility: "Liaisons with systems software to isolate program tasks and feeds load levels back to commanders.",
          difficultyLevel: "Medium",
          keyFilesFolders: ["pkg/kubelet/", "configs/"],
          dependencies: ["Containerd Runtime", "CRI-O System"]
        },
        {
          name: "Virtual Traffic Coordinator",
          iconName: "globe",
          purpose: "Acts as a traffic cop, routing incoming visitors around server traffic jams.",
          responsibility: "Ensures network queries flow perfectly only to healthy computers, shielding failed ones.",
          difficultyLevel: "Hard",
          keyFilesFolders: ["pkg/proxy/", "networks/"],
          dependencies: ["iptables", "IPVS Networks"]
        },
        {
          name: "Auto-Scaler & Helper Agent",
          iconName: "cpu",
          purpose: "Saves money by turning off unneeded servers, and adds power when usage spikes.",
          responsibility: "Constantly queries system hardware logs and requests extra pods during busy rushes.",
          difficultyLevel: "Medium",
          keyFilesFolders: ["pkg/controller/scaler/"],
          dependencies: ["Metrics Server API", "Resource Monitor"]
        }
      ],
      dependencyMap: {
        description: "How Kubernetes ships packages safely: The Central Command Controller listens to your instructions, then directs Worker Pod Deployers to launch systems. Next, the Virtual Traffic Coordinator handles incoming web connections, while the Auto-Scaler tracks limits and triggers Command tasks to add nodes.",
        interactions: [
          { from: "Central Command Controller", to: "Worker Pod Deployers", flowDesc: "Issues precise deployment guides to spin up isolated container instances" },
          { from: "Worker Pod Deployers", to: "Auto-Scaler & Helper Agent", flowDesc: "Shares system load and CPU numbers to evaluate performance limits" },
          { from: "Auto-Scaler & Helper Agent", to: "Central Command Controller", flowDesc: "Requests extra app instances during peak traffic hours" },
          { from: "Virtual Traffic Coordinator", to: "Worker Pod Deployers", flowDesc: "Routes incoming visitor traffic only to container pods that are completely healthy" }
        ]
      }
    };
  }

  if (clean.includes("typescript")) {
    return {
      projectName: "TypeScript",
      analogy: "TypeScript is like a real-time smart grammar check and high-visibility blueprint designed for architectural engineers. Instead of assembling a complex cargo crane by freehand vision and waiting until you try to lift a 10-ton steel slab to discover you bought the wrong sized bolts (which crashes the crane), the smart blueprint alerts you of mismatched thread sizes, missing brackets, and loose nuts as you draw.",
      whatItDoes: "It is a smart assistant designed to help programmers write safer scripts for websites. It points out spelling errors, logic mismatches, and broken pages as they type, protecting software from breaking prior to release.",
      whoUsesIt: ["Software Engineers", "React Front-end Teams", "Web Creators", "Programming Students"],
      whyItExists: "The primary language of the web, JavaScript, is extremely relaxed. It lets developers write loose instructions with silent typos. These errors hide in the file, only to crash the entire checkout screen for real users when they try to place an order.",
      problemSolved: "Hunting through millions of lines of custom code to resolve a single out-of-order bracket or spelling typo that broke a customer's browser.",
      solutionProvided: "Lays down a protective safety grid around your workspace. If you accidentally write instructions that send word text where a pricing number is expected, it flags the mismatch instantly.",
      simpleFeatures: [
        { title: "Autofill & Spellcheck for Coding", desc: "Warns developers of letters misentered or paths broken long before the app is compiled or served." },
        { title: "Explicit Project Maps", desc: "Creates strict lists of what data is expected where, making it incredibly easy for multiple teams to work together with zero friction." },
        { title: "Confident Re-writing", desc: "Allows renaming file variables across thousands of sheets safely, knowing the environment will point out every leftover link." }
      ],
      coreModules: [
        {
          name: "Syntax Blueprinter & Parser",
          iconName: "code",
          purpose: "Translates characters in raw script sheets into an organized, logical structural tree.",
          responsibility: "Verifies every parenthesis, bracket, and comma matches so compiler analysis can occur.",
          difficultyLevel: "Hard",
          keyFilesFolders: ["src/compiler/parser.ts", "scanner.ts"],
          dependencies: ["Lexical Scanner", "AST Builder"]
        },
        {
          name: "Type Integrity Scanner",
          iconName: "shield",
          purpose: "Verifies spellings, variable assignments, and structure formats in real-time.",
          responsibility: "Flags immediate mistakes and alerts builders of mismatched letters or wrong formulas.",
          difficultyLevel: "Hard",
          keyFilesFolders: ["src/compiler/checker.ts", "binder.ts"],
          dependencies: ["Types Assigner", "Interference Engine"]
        },
        {
          name: "Universal Code Translator",
          iconName: "layers",
          purpose: "Cleans up strict helper elements and outputs basic vanilla JavaScript.",
          responsibility: "Converts advanced TypeScript specifications so standard web browsers can run items cleanly.",
          difficultyLevel: "Medium",
          keyFilesFolders: ["src/compiler/emitter.ts", "transformer.ts"],
          dependencies: ["SourceMaps Generator", "JavaScript Optimizer"]
        },
        {
          name: "Smart Editor Assistant (LSP)",
          iconName: "terminal",
          purpose: "Feeds red alert flags and autocompletes into coding applications as you type.",
          responsibility: "Updates error lists instantly on every keystroke, before the programmer even hits save.",
          difficultyLevel: "Medium",
          keyFilesFolders: ["src/services/"],
          dependencies: ["VSCode Compiler Services", "Language Server Protocol"]
        }
      ],
      dependencyMap: {
        description: "How TypeScript checks your files in real-time: The Syntax Blueprinter first parses your typing into a logical tree. The Type Integrity Scanner inspects this tree for errors, alerting the Smart Editor Assistant to draw red squiggly underlines, while the Code Translator bundles clean outputs once checks clear.",
        interactions: [
          { from: "Syntax Blueprinter & Parser", to: "Type Integrity Scanner", flowDesc: "Provides a structured map of code properties to examine" },
          { from: "Type Integrity Scanner", to: "Smart Editor Assistant (LSP)", flowDesc: "Hands over real-time error lists to show in the code editor workspace" },
          { from: "Type Integrity Scanner", to: "Universal Code Translator", flowDesc: "Approves files for translation once all type reviews are completely free of errors" }
        ]
      }
    };
  }

  // Fallback / Scanned Custom repository overview
  return {
    projectName: fullName,
    analogy: "This repository behaves like an organized, custom mechanical blueprint. Instead of throwing loose cogwheels, nuts, cables, and levers into a messy heap (making the machine break down and impossible to maintain), this blueprint files all working cogs into labeled drawers, laying out precise maps of what pulls what.",
    whatItDoes: "Provides a robust, structured digital framework to configure a scalable software program. It maps out where users log in, where data records are safely processed, and where active visual displays reside, grouping everything in perfect modules.",
    whoUsesIt: ["System Organizers", "Independent Project Coders", "Software Teams", "Technical Leads"],
    whyItExists: "If unorganized, software code naturally turns into a messy 'spaghetti' pile where modifying a single line of text can accidentally crash a component on the other side of the platform.",
    problemSolved: "Disorganized file networks, overlapping security controls, and tangled layout scripts that slow progress and build bugs.",
    solutionProvided: "Institutes a stable developer layout that partitions data, security rules, and visual screens into isolated blocks, providing a healthy sandbox for growth.",
    simpleFeatures: [
      { title: "Separated File Layouts", desc: "Keeps clean boundaries between visual design buttons and backend mathematical operations." },
      { title: "Scalable Growth Foundation", desc: "Employs modular designs that let you add dozens of new features without breaking existing logic." },
      { title: "Clean Getting-Started Guides", desc: "Features setup scripts so any new engineer can boot the project up on their laptop in minutes." }
    ],
    coreModules: [
      {
        name: "User Interface Display (Frontend)",
        iconName: "layout",
        purpose: "Renders buttons, forms, and pages, and listens to user mouse clicks.",
        responsibility: "Keeps visual modules aligned, responsive, and animated whenever user inputs occur.",
        difficultyLevel: "Easy",
        keyFilesFolders: ["src/components/", "src/App.tsx"],
        dependencies: ["React Core", "Tailwind CSS", "Lucide Icons"]
      },
      {
        name: "Application API Router (Backend)",
        iconName: "server",
        purpose: "Coordinates requests, processes orders, and double-checks authentication codes.",
        responsibility: "Verifies form fields and cleans up cluttered entries before saving data.",
        difficultyLevel: "Medium",
        keyFilesFolders: ["src/api/", "server.ts"],
        dependencies: ["Express Web Engine", "CORS Guard"]
      },
      {
        name: "Durable Database Storage (Data)",
        iconName: "database",
        purpose: "Acts as a digital filing cabinet, keeping accounts, notes, and records intact after restart.",
        responsibility: "Performs secure updates, runs fast backups, and orders entries under labels.",
        difficultyLevel: "Medium",
        keyFilesFolders: ["src/db/", "migrations/"],
        dependencies: ["SQLite Engine", "Drizzle ORM"]
      },
      {
        name: "Alerts & Notifications Agent (Services)",
        iconName: "zap",
        purpose: "Informs users of system events, tracks achievements, and sends confirmation emails.",
        responsibility: "Dispatches warnings immediately when metrics rise or account events occur.",
        difficultyLevel: "Easy",
        keyFilesFolders: ["src/services/notifications/"],
        dependencies: ["Web Push Library", "Email Sender Module"]
      }
    ],
    dependencyMap: {
      description: "How this repository modules work together: The User Interface captures what you do and forwards it to the Application API Router. The API Router verifies your access, executes data handshakes on the Database Storage Layer, and tells the Alerts Agent to send confirmation alerts to the visitor.",
      interactions: [
        { from: "User Interface Display (Frontend)", to: "Application API Router (Backend)", flowDesc: "Transmits user clicks and secure parameters over web standards" },
        { from: "Application API Router (Backend)", to: "Durable Database Storage (Data)", flowDesc: "Requests storage validation, reads, or column updates" },
        { from: "Application API Router (Backend)", to: "Alerts & Notifications Agent (Services)", flowDesc: "Instructs email or text notification cues when tasks complete successfully" }
      ]
    }
  };
}

// 2. Get Advanced Educational Metadata
function getEducationalMetadata(fullName: string): EducationalMetadata {
  const clean = fullName.toLowerCase();

  if (clean.includes("next.js") || clean.includes("nextjs")) {
    return {
      projectType: "Full-Stack React Framework",
      maintenanceScore: "99/100",
      badges: ["Enterprise Grade", "Turbopack Compiler", "RSC Architecture"],
      architectureNodes: [
        { name: "Global Edge CDN", desc: "Vercel / Cloudflare Edge Routing", icon: Globe },
        { name: "Server Core Node", desc: "NextJS Node.js Server Run", icon: Server },
        { name: "Server Components", desc: "HTML Streaming & SSR Nodes", icon: Cpu },
        { name: "Client Browser UI", desc: "Hydrated active SPA viewports", icon: Layout }
      ],
      requestFlow: [
        { step: "User Route Trigger", label: "Client browser requests a modern route containing async data fields." },
        { step: "Edge Middleware CDN", label: "Validates headers, evaluates redirects, and runs geolocation custom routing rules." },
        { step: "RSC Server Render", label: "Resolves Server Components, fetches API sources, and compiles raw DOM streams." },
        { step: "Asset HTML Pipeline", label: "Streams lightweight HTML response immediately to client to show paint instantly." },
        { step: "Client JS Hydration", label: "Browser runs dynamic scripts to pair interactive states with HTML nodes." }
      ],
      coreComponents: [
        { title: "RSC Renderer Core", desc: "Maintains server-rendering pipelines for isolated node streams." },
        { title: "Turbopack Rust Compiler", desc: "Speeds up local builds utilizing custom incremental graphs." },
        { title: "Path Prefetcher Hub", desc: "Detects active user viewport links and fetches code pages in background." },
        { title: "Middleware Gateway", desc: "Handles serverless pre-route evaluations like cookie verification." }
      ],
      techStackWhy: [
        { category: "Framework Core", tech: "React 19", why: "Leverages React Server Components for server-first rendering pipelines." },
        { category: "Dev Bundler", tech: "Rust Turbopack", why: "Bypasses legacy slow JS trees to compile modifications in milliseconds." },
        { category: "Language Type", tech: "TypeScript", why: "Fosters precise static parameters for nested routing safety." },
        { category: "Hosting Layer", tech: "Vercel Platform", why: "Delivers zero-auth setups for edge deployments." }
      ],
      learningConcepts: ["Server-Side Rendering (SSR) Pipelines", "React Hydration Cycle", "Incremental Static Regeneration (ISR)", "Edge Code Execution Rules", "Optimizer Bundling Theory"],
      difficulty: "Intermediate",
      prerequisites: ["React Hook state rules", "Asynchronous Promise loops", "Modern CSS flex grids"],
      roadmap: [
        { phase: "Week 1", title: "Nested Layout Routing & Dynamic Paths" },
        { phase: "Week 2", title: "Server Actions & API Proxies Integration" },
        { phase: "Week 3", title: "Asset Optimizers (Image, Fonts, Scripts) Setup" },
        { phase: "Week 4", title: "Edge Mid-deployment & Cache Key Tuning" }
      ],
      relatedIdeas: ["Static Grid Portfolio Site", "Microservices Dashboard Wrapper", "Optimized Content Delivery Portal"],
      similarReposDetail: [
        { fullName: "remix-run/remix", whatItDoes: "Composability-heavy React framework centered straight on pure web standards.", whySimilar: "Focuses on pre-fetching data payloads and rendering pages on the server.", techStack: ["React", "Node.js", "TypeScript"], difficulty: "Intermediate" },
        { fullName: "nuxt/nuxt", whatItDoes: "Intuitive SSR framework optimized for universal Vue applications.", whySimilar: "Delivers almost identical nested layout folders and pre-compilations styled on Vue.", techStack: ["Vue", "Vite", "TypeScript"], difficulty: "Intermediate" }
      ],
      scalabilityStudy: {
        cachingStrategy: "Utilizes ISR (Incremental Static Regeneration) to cache computed pages across edge CDNs, refreshing assets in the background on configuration timer cues.",
        concurrencyMethod: "Node-based server cluster pooling combined with serverless edge handlers that scale independently without loading central database locks.",
        bottleneckMitigation: "Protects target APIs by executing links prefetching natively in lightweight client-side service worker threads."
      },
      designDecisions: {
        monorepoAdvantages: "Maintains the core framework, examples, and Swift/swc Rust tools in a single Turborepo to enforce matching versions.",
        separationOfConcerns: "Divides client UI layers from server-rendering blocks via strict file-type annotations (e.g., 'use client').",
        securityLayerDesign: "Hides proprietary corporate API credentials inside serverless Server Actions endpoints, completely shielding tokens from the browser script compiler."
      }
    };
  }

  if (clean.includes("supabase")) {
    return {
      projectType: "Backend-as-a-Service (BaaS) Platform",
      maintenanceScore: "97/100",
      badges: ["Postgres Ecosystem", "CDC Realtime Streams", "JWT Identity Guard"],
      architectureNodes: [
        { name: "Browser App / SDK", desc: "Type-safe database JS client query", icon: Layout },
        { name: "Kong Proxy Gateway", desc: "Reverse proxy token verifier", icon: Settings },
        { name: "PostgREST & GoTrue", desc: "Haskell and Go translation blocks", icon: Server },
        { name: "PostgreSQL Instance", desc: "Relational database with RLS parameters", icon: Database }
      ],
      requestFlow: [
        { step: "SDK Invokes Query", label: "Client browser writes structured query chains like .from('users').select()." },
        { step: "Kong JWT Evaluation", label: "Proxy gateway verifies the API keys and decodes user identity tokens." },
        { step: "PostgREST Conversion", label: "Lightweight engine translates incoming HTTP parameters straight into SQL phrases." },
        { step: "RLS SQL Check", label: "Postgres checks Row-Level Security rules matching user credentials before executing." },
        { step: "JSON Broadcast Stream", label: "Database returns structured columns instantly, formatted on-the-fly as JSON." }
      ],
      coreComponents: [
        { title: "PostgREST Engine", desc: "Transforms traditional relational tables into instantaneous REST APIs." },
        { title: "GoTrue Auth Portal", desc: "Go microservice managing session tokens, logins, and key recovery." },
        { title: "Realtime CDC Broadcast", desc: "Elixir Phoenix engine listening to Postgres WAL states to emit mutations." },
        { title: "S3 Storage Gateway", desc: "Custom node middleware mapping S3 uploads with Postgres access checks." }
      ],
      techStackWhy: [
        { category: "Datastore Engine", tech: "PostgreSQL", why: "Leverages standard SQL, ACID compliance, and robust Row-Level Security." },
        { category: "REST API Compiler", tech: "PostgREST (Haskell)", why: "Slashes memory footprint and translates calls recursively into native SQL." },
        { category: "Streaming Core", tech: "Elixir Phenix", why: "Handles millions of concurrent WebSocket pipelines with lightweight Erlang threads." },
        { category: "System Wrapper", tech: "Docker Compose", why: "Offers self-hosting setups exactly matching cloud runtime patterns." }
      ],
      learningConcepts: ["Relational Database Schemas", "Row-Level Security (RLS) policies", "CDC (Change-Data-Capture) Systems", "JSON Web Token (JWT) Authentications", "WebSocket Broadcast Pipes"],
      difficulty: "Intermediate",
      prerequisites: ["Structured SQL commands", "Node.js environment basics", "REST API structures"],
      roadmap: [
        { phase: "Week 1", title: "PostgreSQL Tables, Relations, and RLS Setup" },
        { phase: "Week 2", title: "User Signups and JWT Active Session Hooks" },
        { phase: "Week 3", title: "Secure File Storage Bucket Rules" },
        { phase: "Week 4", title: "Realtime WebSocket Mutations Subscriptions" }
      ],
      relatedIdeas: ["Relational API Mirror", "Instant Password Security Service", "Live Database Change Broadcasting Module"],
      similarReposDetail: [
        { fullName: "pocketbase/pocketbase", whatItDoes: "Compact open-source Go database compiled with SQLite and built-in Admin UI.", whySimilar: "Offers simple, fast real-time synchronization in a single executable.", techStack: ["Go", "SQLite", "Svelte"], difficulty: "Beginner" },
        { fullName: "appwrite/appwrite", whatItDoes: "Dockerized comprehensive platform delivering robust cloud utilities.", whySimilar: "Delivers consolidated auth, data tables, and secure storage containers.", techStack: ["TypeScript", "PHP", "Docker"], difficulty: "Intermediate" }
      ],
      scalabilityStudy: {
        cachingStrategy: "Integrates Supabase cache layers and Redis queues to offload repeated queries before reaching the transactional core.",
        concurrencyMethod: "Erlang-based Phoenix nodes that process millions of WebSocket broadcasts with predictable memory consumption.",
        bottleneckMitigation: "Implements connection pool managers (PgBouncer) to protect Postgres from crashing under high microservice container scalability spikes."
      },
      designDecisions: {
        monorepoAdvantages: "Unifies different tools (Auth, Studio dashboard, Realtime modules, JS SDKs) under one roof to assure integrated releases.",
        separationOfConcerns: "Maintains isolated, microservice docker boxes (Kong, postgrest, gotrue) to let developers scale only what is lagging.",
        securityLayerDesign: "Enforces security parameters directly within database tables via SQL RLS, guaranteeing that even compromised API keys cannot bypass security checks."
      }
    };
  }

  // Fallback / Custom Scanned repositories advanced technical blueprint
  return {
    projectType: "Structured Cloud-Native System",
    maintenanceScore: "95/100",
    badges: ["Modular Blueprint", "Clean Architecture", "Production Ready"],
    architectureNodes: [
      { name: "Frontend Visualizer", desc: "Modular web dashboards built in React", icon: Layout },
      { name: "Backend Coordinator", desc: "API routers delivering secure JSON nodes", icon: Server },
      { name: "Query Scraper Engine", desc: "Active metric track buffers", icon: Cpu },
      { name: "Relational Datastore", desc: "Durable storage and system credentials", icon: Database }
    ],
    requestFlow: [
      { step: "User Action Client", label: "Browser sends API parameters invoking a specific operational process." },
      { step: "Endpoint Middleware Auth", label: "Backend server checks rate metrics and validates security tokens." },
      { step: "Data Scraper Queries", label: "Reroutes target directives to query database parameters." },
      { step: "Serialized Packaging", label: "Transforms binary database variables into standardized, fast JSON files." },
      { step: "Layout Reconciliation", label: "Frontend receives JSON package and recreates UI nodes without reloading the page." }
    ],
    coreComponents: [
      { title: "Modular UI Dashboard", desc: "Responsive component nodes for plotting charts and data tables." },
      { title: "API Routing Central", desc: "Server router managing clean endpoints and input check gates." },
      { title: "Query Processor Node", desc: "Handles database checks and optimizes repetitive lists." },
      { title: "Durable Datastore Config", desc: "Preserves user settings, credentials, and persistent data indices." }
    ],
    techStackWhy: [
      { category: "Frontend Interface", tech: "React & Tailwind", why: "Allows building responsive, modular dashboards styled with inline tags." },
      { category: "Systems Backend", tech: "NodeJS / Go Core", why: "Enables fast runtime compilation, concurrent threads, and stable API serving." },
      { category: "Datastore Vault", tech: "PostgreSQL", why: "Ensures secure, ACID-compliant tabular records for configuration files." },
      { category: "Deployment Container", tech: "Docker Container", why: "Ensures identical environmental behaviors between local labs and production." }
    ],
    learningConcepts: ["Modular Architecture Design", "Interface & Route Segregation", "Relational Schema Controls", "Security Endpoint Gates", "Asset Packaging Optimizations"],
    difficulty: "Intermediate",
    prerequisites: ["Modular JavaScript rules", "Durable DB transaction logic", "Docker basic operations"],
    roadmap: [
      { phase: "Week 1", title: "API Gateway Routes & Rate Handlers" },
      { phase: "Week 2", title: "Database Schema Modeling & Relational Ties" },
      { phase: "Week 3", title: "Responsive Dashboard Layout and Navigation" },
      { phase: "Week 4", title: "Production Containerization and Security Audit" }
    ],
    relatedIdeas: ["Distributed Observability Dashboard", "Optimized Micro-API Route Gateway", "SaaS Boilerplate Blueprint"],
    similarReposDetail: [
      { fullName: "promlens/promlens", whatItDoes: "Visual query compiler and troubleshooting node dedicated to metrics data.", whySimilar: "Shares modular dashboard rendering and telemetry analytical features.", techStack: ["Go", "React", "PromQL"], difficulty: "Intermediate" },
      { fullName: "grafana/grafana", whatItDoes: "World-class dashboard engine and systems performance tracking charts.", whySimilar: "Implements comprehensive telemetry charts and real-time dashboard grids.", techStack: ["Go", "TypeScript", "SQL"], difficulty: "Advanced" }
    ],
    scalabilityStudy: {
      cachingStrategy: "Preserves heavy dashboard layouts on local client-side state engines and wraps hot backend endpoints in Redis key-value stores.",
      concurrencyMethod: "Runs decoupled server routers that process incoming requests asynchronously, leaving database queries to pool connections.",
      bottleneckMitigation: "Enforces rate-limiting proxies at the edge to reject system attacks before they impact the primary server cores."
    },
    designDecisions: {
      monorepoAdvantages: "Consolidates configuration files, deployment Dockerfiles, and dashboard code in one monorepo, speeding up team communication.",
      separationOfConcerns: "Keeps a strict division: components only handle HTML updates, while API client utilities manage data handshakes.",
      securityLayerDesign: "Authenticates every incoming POST request using secure authorization tokens, validating schema types before saving."
    }
  };
}

// Recursive Folder Tree Explorer Element
interface FolderTreeProps {
  node: FileTreeNode;
  depth: number;
  key?: React.Key;
}

function FolderTree({ node, depth }: FolderTreeProps) {
  const [isOpen, setIsOpen] = useState(depth === 0 || node.name === "src" || node.name === "packages");
  const hasChildren = node.type === 'folder' && node.children && node.children.length > 0;

  return (
    <div className="select-none font-mono text-xs">
      <div
        onClick={() => {
          if (hasChildren) setIsOpen(!isOpen);
        }}
        className={`flex items-center justify-between py-1.5 px-2 rounded-lg cursor-pointer transition-colors ${node.type === 'folder'
            ? 'hover:bg-white/[0.03] text-purple-200'
            : 'hover:bg-white/[0.02] text-gray-300'
          }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        <div className="flex items-center gap-2 overflow-hidden">
          {node.type === 'folder' ? (
            <>
              <ChevronDown
                className={`h-3.5 w-3.5 text-gray-500 transition-transform duration-200 shrink-0 ${isOpen ? 'transform rotate-0' : 'transform -rotate-90'
                  }`}
              />
              <Folder className="h-4 w-4 text-indigo-400 shrink-0" />
            </>
          ) : (
            <>
              <span className="w-3.5 shrink-0" />
              <File className="h-4 w-4 text-gray-400 shrink-0" />
            </>
          )}
          <span className="truncate break-all">{node.name}</span>
        </div>

        {node.size && (
          <span className="text-[10px] text-gray-500 bg-white/[0.02] px-2 py-0.5 rounded border border-white/[0.04] shrink-0 font-mono">
            {node.size}
          </span>
        )}
      </div>

      {node.type === 'folder' && isOpen && node.children && (
        <div className="mt-0.5 border-l border-white/[0.04] ml-4.5 sm:ml-6">
          {node.children.map((child, idx) => (
            <FolderTree key={idx} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

interface ModuleDetailedSpec {
  longDescription: string;
  analogy: string;
  whyCritical: string;
  bestPractices: string[];
  commonTasks: string[];
  mockCodeBlock: string;
  mockCodeLanguage: string;
  executionFlow: string[];
}

function getModuleDetailedSpecs(projectName: string, mName: string): ModuleDetailedSpec {
  const pName = projectName.toLowerCase();
  const name = mName.toLowerCase();

  // NEXT.JS PRESETS
  if (pName.includes("next")) {
    if (name.includes("frontend") || name.includes("client")) {
      return {
        longDescription: "This module manages user presentation, stylesheet alignment, and client interaction bindings. Utilizing React 19 rules, it drives fluid animations, captures pointer click streams, and translates keyboard typing inputs directly into visual UI views.",
        analogy: "Think of it as the interior cabin of a luxury car: the high-definition touchscreen panel, steering wheel, and custom seats. It is what you touch, interact with, and see in motion, but it relies on a hidden engine under the hood to actually travel.",
        whyCritical: "If the client UI fails or hydrate mismatches occur, the page will appear frozen or broken. Click events won't fire, forms will drop characters, and transition loads will fail, resulting in lost users.",
        bestPractices: [
          "Delegate heavy calculations and state compiles to backend modules where possible.",
          "Keep useEffect triggers stable; always clean up event listeners to protect browser performance.",
          "Style components with responsive Tailwind grids for smooth layout adapters on all view sizes."
        ],
        commonTasks: [
          "Rendering responsive dashboard cards and listings",
          "Capturing form inputs and binding validation routines",
          "Firing dynamic entering motion animations and transitions"
        ],
        mockCodeBlock: `// Example of Client Component (src/components/InteractiveList.tsx)
"use client";
import { useState } from "react";
import { motion } from "motion/react";

export function InteractiveButton() {
  const [clicks, setClicks] = useState(0);
  return (
    <motion.button 
      whileHover={{ scale: 1.05 }}
      onClick={() => setClicks(c => c + 1)}
      className="px-5 py-2.5 bg-purple-600 rounded-xl text-white font-bold shadow-md"
    >
      Clicked {clicks} times
    </motion.button>
  );
}`,
        mockCodeLanguage: "tsx",
        executionFlow: [
          "Page loads raw static HTML template elements first",
          "Pipes layout visual cards before scripts are parsed",
          "Hydrates interactive scripts onto visual framework DOM",
          "Wires up click parameters to active hook state counters"
        ]
      };
    }
    if (name.includes("router") || name.includes("routing")) {
      return {
        longDescription: "The Next.js App Router provides directory-based routing, server components integration, dynamic URL parameters matching, and intelligent route pre-fetching. It switches pages at client speeds of a single page application.",
        analogy: "Think of a smart subway station operator. The moment they spot a passenger coming close to a platform line, they pre-position an open shuttle train on the track so that when the customer boards, departure is immediate.",
        whyCritical: "A broken router freezes transitions, causing full browser refreshing, heavy cellular data drains, and an unoptimized laggy feel.",
        bestPractices: [
          "Employ standard Link tags for native web prefetching of viewport targets.",
          "Utilize persistent layout files to avoid full component rebuilds across URLs.",
          "Check dynamic segment fallback blocks to shield pages from missing ID entries."
        ],
        commonTasks: [
          "Matching web URLs like /shop/product to filesystem paths",
          "Conducting background pre-fetching of linked resources",
          "Compiling layout nesting rules for complex workspaces"
        ],
        mockCodeBlock: `// app/blog/[id]/page.tsx
import { getBlogPost } from "@/lib/db";
import { notFound } from "next/navigation";

export default async function BlogPostPage({ params }: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params;
  const post = await getBlogPost(id);
  if (!post) notFound();
  
  return (
    <article className="max-w-2xl mx-auto py-8 font-sans">
      <h1 className="text-3xl font-black text-white">{post.title}</h1>
      <p className="mt-4 text-gray-300 leading-relaxed">{post.content}</p>
    </article>
  );
}`,
        mockCodeLanguage: "typescript",
        executionFlow: [
          "Visitor triggers routing link to path /blog/112",
          "Router maps target parameter to [id]/page.tsx",
          "Executes async database query on server-side engine",
          "Transmits stream blocks dynamically to browser grid viewport"
        ]
      };
    }
    if (name.includes("api") || name.includes("action") || name.includes("gateway")) {
      return {
        longDescription: "Bridges client views to secure back-end systems. API route handlers (/api/*) and Server Actions run code purely on secure Node.js environments, shielding payment API keys and database credentials.",
        analogy: "Like a secure drive-through teller tube in a bank. You place your instructions inside, the tube moves underground, and the cashiers make ledger changes inside their locked vault. You never enter the secure safe.",
        whyCritical: "If secret API keys are leaked directly to front-end codes, hijackers can steal your databases, drain Stripe portals, and charge massive server costs.",
        bestPractices: [
          "Validate all incoming request bodies using schemas before databases calls.",
          "Confirm active login sessions on every single endpoint script run.",
          "Inject rate-limiter rules on public API paths to curb crawler bots spam."
        ],
        commonTasks: [
          "Handling stripe subscription payment portals hook callouts",
          "Authenticating user credentials securely behind vaults",
          "Executing backend SQL database reads and operations"
        ],
        mockCodeBlock: `// app/api/checkout/route.ts
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    if (!payload.cartItems) {
      return NextResponse.json({ error: "Empty cart dataset" }, { status: 400 });
    }
    
    // Execute backend Stripe transaction securely...
    return NextResponse.json({ success: true, txnId: "ch_9872" });
  } catch (err) {
    return NextResponse.json({ error: "Server crashed" }, { status: 500 });
  }
}`,
        mockCodeLanguage: "typescript",
        executionFlow: [
          "Client uploads encrypted parameter packages to API path",
          "Gateway checks session indicators and cookies headers",
          "Calculates backend algorithms and safe database queries",
          "Returns clean, lightweight success JSON results back"
        ]
      };
    }
    return {
      longDescription: "The Asset & Image Optimizer compiles raw development scripts, compresses heavy source photos to next-generation AVIF/WebP formats, and bundles dependencies in highly optimized chunks.",
      analogy: "A genius professional packer. Instead of loading loose puffy hats and heavy bags, they vacuum-compress everything into tiny airtight blocks so everything fits perfectly in your tiny trunk space.",
      whyCritical: "Failing to optimize assets translates to massive 12MB page loads on mobile phones, burning customer cell plans and crashing sluggish browser screens.",
      bestPractices: [
        "Declare width/height dimensions on images to block browser page jump shunts.",
        "Target next-generation graphics formats over heavy raw JPEG files.",
        "Configure custom CDN headers to store optimized assets near customers."
      ],
      commonTasks: [
        "Converting heavy image uploads on-the-fly to tiny WebP assets",
        "Trimming unneeded scripts and libraries from production bundles",
        "Managing compile flags during incremental turbopack builds"
      ],
      mockCodeBlock: `// next.config.js - Custom Asset Settings
/** @type {import('next').NextConfig} */
module.exports = {
  images: {
    formats: ['image/avif', 'image/webp'],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'assets.brand.com',
      },
    ],
  },
};`,
      mockCodeLanguage: "javascript",
      executionFlow: [
        "Page requests graphic URL from external web server",
        "Optimizer grabs original and parses client screens width",
        "Resizes file on-the-fly to modern WebP compressed values",
        "Delivers custom lightweight photo block with long cache terms"
      ]
    };
  }

  // SUPABASE PRESETS
  if (pName.includes("supabase")) {
    if (name.includes("auth") || name.includes("security")) {
      return {
        longDescription: "A fortress module centered on validating client signatures. Supabase Auth processes email signups, passwords, OAuth (Google/Github) redirects, and manages active session tokens (JWT) recursively.",
        analogy: "Like a highly trained ticket inspector. They check your ID passport once at the terminal gate, glue a VIP water-resistant band to your wrist, and let you skip deep checks on all subpanels.",
        whyCritical: "Any vulnerability here means rogue intruders can simulate active user sessions, stealing billing data and altering private workspaces.",
        bestPractices: [
          "Secure sensitive UI paths with persistent session checks.",
          "Keep redirect URLs strictly whitelisted under SSL-only targets.",
          "Maintain user logs securely and verify password minimum strengths."
        ],
        commonTasks: [
          "Piping secure passkey logins with single calls",
          "Generating account passwords recovery email links",
          "Integrating OAuth Google web redirects and flows"
        ],
        mockCodeBlock: `// Simple User Authentication Flow
import { createClient } from "@supabase/supabase-js";
const supabase = createClient("https://p_url.supabase.co", "anon-key");

export async function signUpUser(email, password) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
  });
  if (error) throw new Error(error.message);
  return data.user;
}`,
        mockCodeLanguage: "typescript",
        executionFlow: [
          "User submits login form email/password",
          "Auth center hashes and matches key against salting archives",
          "Compiles secure JWT session tokens",
          "Stores user parameters inside local browser cookie cells"
        ]
      };
    }
    if (name.includes("relational") || name.includes("database")) {
      return {
        longDescription: "The absolute data core. Powered by standard PostgreSQL, handles relational tables, structured schemas, foreign key integrity, and implements Row-Level Security (RLS) rules directly in database engines.",
        analogy: "A modern bulletproof bank vault room. Inside, every safe-deposit box has a personalized key. Even if you walk past guards into the vault area, you can ONLY open your own box. Everyone else's is sealed.",
        whyCritical: "Without active SQL security policies (RLS), an unchecked query can fetch any password hash, billing index, or user log.",
        bestPractices: [
          "Ensure RLS is turned on for every newly constructed PostgreSQL table.",
          "Always apply database indexes on frequently queried columns to keep speed.",
          "Separate migrations into distinct files with rollback security clauses."
        ],
        commonTasks: [
          "Enforcing strict database columns and foreign constraints",
          "Enabling Row-Level Security (RLS) filters on records",
          "Compiling table relations for complex lookup actions"
        ],
        mockCodeBlock: `-- Row-Level Security Policy Definition
ALTER TABLE todo_list ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage only their own todos"
ON todo_list FOR ALL
USING (auth.uid() = creator_id);`,
        mockCodeLanguage: "sql",
        executionFlow: [
          "Client browser submits record query command",
          "PostgreSQL parses JWT identity parameters in real-time",
          "Injects security uid comparison on database tables",
          "Retrieves only records matching user identifier rules"
        ]
      };
    }
    if (name.includes("realtime") || name.includes("broadcast") || name.includes("dispatcher")) {
      return {
        longDescription: "The immediate data router. Monitors standard PostgreSQL transaction logs (WAL) and instantly marshals rows modifications over WebSockets directly to browser screens.",
        analogy: "Like a live trader shouting numbers inside a trading pit. No one has to call back to ask for updates; they scream out changes the second they happen.",
        whyCritical: "Broken sockets halt direct collaborations, drop chat messages into queues, and leave metrics panels displaying old outdated info.",
        bestPractices: [
          "Subscribe only to clean relevant table selections to reduce server CPU load.",
          "Always close client socket connections on React unmounts to prevent leaks.",
          "Store updates in local states cache for smooth offline recovery."
        ],
        commonTasks: [
          "Streaming instant user chat messaging feeds",
          "Piping server achievement indicators to displays",
          "Pulsing metric telemetry curves in instant unison"
        ],
        mockCodeBlock: `// Subscribing to instant database changes
import { createClient } from "@supabase/supabase-js";
const supabase = createClient("https://app.supabase.co", "key");

const channel = supabase
  .channel('live-tasks')
  .on('postgres_changes', { event: '*', schema: 'public', table: 'todos' }, payload => {
    console.log('Realtime change spotted:', payload);
  })
  .subscribe();`,
        mockCodeLanguage: "typescript",
        executionFlow: [
          "Client updates todo database row via secure gateway",
          "Postgres commits change writes to active WAL logs",
          "Dispatcher intercepts log write and converts to socket payload",
          "Pushes update package of values to subscribed browser screens"
        ]
      };
    }
    return {
      longDescription: "An isolated, secure digital warehouse optimized for raw binary blobs like user image avatars, PDF documents, spreadsheets, and video files. Integrated with Postgres RLS.",
      analogy: "Think of a smart hotel storage locker. The lobby clerk verifies your room key card and signatures, walks into the back closet, and returns with your secure case.",
      whyCritical: "Unprotected storage lets malicious actors scan target URLs to crawl and download other clients' sensitive PDFs or receipts.",
      bestPractices: [
        "Make buckets private by default unless explicitly public graphic assets.",
        "Emit temporary signed paths for security documents so they expire in minutes.",
        "Enforce strict file type and size boundaries on uploads to block malware."
      ],
      commonTasks: [
        "Uploading user graphic avatars with safety constraints",
        "Generating single-use expiry download links",
        "Cataloguing binary documents cleanly into folders"
      ],
      mockCodeBlock: `// Upload invoice to private file bucket
const { data, error } = await supabase
  .storage
  .from('user_invoices')
  .upload('user_98/invoice_may.pdf', pdfFileBuffer, {
    contentType: 'application/pdf',
    upsert: true
  });`,
      mockCodeLanguage: "typescript",
      executionFlow: [
        "Client packages a file object into HTTP multipart streams",
        "Storage gate checks file byte size limits and types",
        "Applies PostgreSQL RLS permissions check to authorize write",
        "Saves asset into cloud storage cells and locks keys"
      ]
    };
  }

  // KUBERNETES PRESETS
  if (pName.includes("kubernetes")) {
    if (name.includes("command") || name.includes("controller") || name.includes("central")) {
      return {
        longDescription: "The cluster brain. Keeps tracking desired container states, schedules nodes deployment, and coordinates API systems. Stores all absolute metadata in high-consistency etcd arrays.",
        analogy: "The busy control tower of a capital airport. They know exactly which runway is clear, which airplane is idling, and which flights are circling, and keep scheduling perfectly synchronized.",
        whyCritical: "If command center crashes, the cluster freezes. Healthy containers stay online, but crashed machines can't be healed, leading to rapid outages.",
        bestPractices: [
          "Deploy controller instances across odd numbers to guarantee etcd majorities.",
          "Restrict controller API access using TLS certificates credentials only.",
          "Maintain daily backups of master configurations manifests."
        ],
        commonTasks: [
          "Analyzing incoming YAML configurations manifests",
          "Supervising resource scheduling and nodes assignments",
          "Logging cluster health statistics to etcd databases"
        ],
        mockCodeBlock: `# Example Deployment Manifest (deployment.yaml)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: core-app-deploy
spec:
  replicas: 4
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
      - name: main-node
        image: node:20-alpine
        ports:
        - containerPort: 3000`,
        mockCodeLanguage: "yaml",
        executionFlow: [
          "Architect dispatches setup manifest over CLI command",
          "API controller parses schema and verifies user keys",
          "Stores desired system count inside central etcd",
          "Triggers deployment loop orders to workers nodes"
        ]
      };
    }
    if (name.includes("worker") || name.includes("pod") || name.includes("deployer")) {
      return {
        longDescription: "Physical deployment executor. Runs on individual compute servers, boots isolated application containers, mounts memory disks, and monitors CPU loads recursively.",
        analogy: "The hard-hat foreman on a factory workshop floor. They accept blueprints from head office, start up machines, and report status loops on sensors.",
        whyCritical: "If worker systems crash, running processes shut down. New program instances cannot boot, dropping user connection lines.",
        bestPractices: [
          "Add definitive memory/CPU limit caps to avoid system lockouts.",
          "Set up automated pod security bounds to lock container processes.",
          "Inject lightweight readiness probes to confirm apps are stable."
        ],
        commonTasks: [
          "Running and pulling container system templates",
          "Conducting routine resource measurements checklists",
          "Arranging persistent local volume directories"
        ],
        mockCodeBlock: `// Conceptual Pod Health check routine
export async function checkPodResources(podId) {
  const info = await hostSystem.getPodUsage(podId);
  if (info.ramBytes > info.ramLimitBytes) {
    await hostSystem.terminatePod(podId);
    console.error("Memory limit passed! Pod recycle triggered.");
  }
  return info;
}`,
        mockCodeLanguage: "typescript",
        executionFlow: [
          "Receives explicit start command from command center",
          "Pulls container image code from secure cloud registry",
          "Launches isolated container in systems sandbox",
          "Monitors RAM and log stdout streams constantly"
        ]
      };
    }
    if (name.includes("traffic") || name.includes("coordinator")) {
      return {
        longDescription: "Manages network routing across server networks. Handles internal domain names resolutions, maps server load-balancer IPs, and steers packets only to completely active, healthy containers.",
        analogy: "A rapid-fire highway tollway director. They look down paths, spot crashes, and dynamically steer cars away from construction zone lanes onto clear paths.",
        whyCritical: "If networking configurations fail, users encounter 503 Gateway Errors. Traffic gets forwarded to unresponsive nodes.",
        bestPractices: [
          "Configure TCP readiness checks so router can isolate broken nodes.",
          "Set up standard CDN/ingress rules for SSL terminate operations.",
          "Leverage load-balancer rules to divide metrics evenly."
        ],
        commonTasks: [
          "Resolving internal domain targets for node-to-node queries",
          "Exposing cluster entry points through Ingress definitions",
          "Updating routing table variables inside iptables engines"
        ],
        mockCodeBlock: `# Routing instructions inside Virtual Traffic Agent
# Route incoming port 80 requests to active pod targets
-A KUBE-SERVICES -d 10.96.0.40/32 -p tcp --dport 80 -j KUBE-SVC-API
-A KUBE-SEP-API -p tcp -m comment -j DNAT --to-destination 10.244.1.12:3000`,
        mockCodeLanguage: "bash",
        executionFlow: [
          "User opens dynamic web address page inside browser",
          "Network proxy captures query and verifies healthy pod lists",
          "Translates target IP destinations at packet speeds",
          "Forwards connection safely to verified container port"
        ]
      };
    }
    return {
      longDescription: "Tracks server parameters and launches additional container pods automatically during user spikes, or scales them down in off-hours to preserve budget.",
      analogy: "Like an accordion instrument that expands when air rushes in, and shrinks back to thin dimensions when the music halts, keeping size matched to action.",
      whyCritical: "Without auto-scaling, your apps will collapse when they go viral, or burn thousands of dollars running idle server banks.",
      bestPractices: [
        "Anchor minimum nodes numbers so basic tasks stay alive.",
        "Set sensible cooldown timers to stop nodes flickering back-and-forth.",
        "Enforce strict priority rules to choose which pods are turned off first."
      ],
      commonTasks: [
        "Querying memory loads across cluster systems",
        "Calculating running limits and resource usage scales",
        "Spawning auxiliary system container nodes dynamically"
      ],
      mockCodeBlock: `# Auto-scaling Parameter manifest (hpa.yaml)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: core-api-scaler
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 3
  maxReplicas: 15
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 80`,
      mockCodeLanguage: "yaml",
      executionFlow: [
        "Scaler agent queries metrics API every few seconds",
        "Spots average CPU values passing the 80% boundary line",
        "Sends write requests to Central Command to add replicas",
        "Fades node count back down when traffic subsides"
      ]
    };
  }

  // TYPESCRIPT PRESETS
  if (pName.includes("typescript")) {
    if (name.includes("parser") || name.includes("blueprint") || name.includes("syntax")) {
      return {
        longDescription: "The syntax scanning core. Reads letters from raw scripts, runs token evaluation, and builds the Abstract Syntax Tree (AST) representing functions, classes, and variables.",
        analogy: "A genius grammar teacher reading hand-written stories. They map out where verbs, nouns, and sub-clauses are, translating loose text sheets into a strict logic skeleton chart.",
        whyCritical: "If parsing fails, code cannot be evaluated. The system won't know where expressions start or end, preventing subsequent inspections.",
        bestPractices: [
          "Ensure your scripts maintain complete syntax integrity before launching parser.",
          "Utilize lightweight parser settings during early coding for fast edits.",
          "Track token depth limits to avoid stack overflows on heavy nested sheets."
        ],
        commonTasks: [
          "Converting raw characters into lexer tokens streams",
          "Assembling Abstract Syntax Tree JSON hierarchies",
          "Spotting missing closures, brackets, or un-ended comments"
        ],
        mockCodeBlock: `// Example parsed AST Node representation
interface VariableDeclarationNode {
  kind: "VariableStatement";
  declarations: [{
    name: "itemPrice",
    type: "NumberKeyword",
    initializer: { kind: "NumericLiteral", value: 99.95 }
  }];
}`,
        mockCodeLanguage: "typescript",
        executionFlow: [
          "Compiler loads characters into lexical scanning buffer",
          "Converts keywords and symbols into discrete token lists",
          "Assembles tokens into nested syntax tree arrays",
          "Wires up code coordinates variables for debugger mapping"
        ]
      };
    }
    if (name.includes("scanner") || name.includes("integrity") || name.includes("type")) {
      return {
        longDescription: "The parameter guardian. Climbs the parsed tree nodes and verifies that inputs, signatures, returns, and variables assignments comply with designated type guidelines.",
        analogy: "The strict supervisor at a puzzle factory. They check the alignment notches of every singular part. If they spot a circle notch pushed into dynamic tri-panels, they alert builders.",
        whyCritical: "Without immediate checks, spelling bugs, null parameters, and structural failures bypass development to crash client screens.",
        bestPractices: [
          "Declare explicit variable types instead of leaning heavily on 'any'.",
          "Employ strict compiler rules like 'strictNullChecks' to find null-pointer crashes.",
          "Make parameters read-only where values shouldn't be altered."
        ],
        commonTasks: [
          "Re-tracing variable assignments over multiple system sheets",
          "Checking signatures accuracy inside library parameters",
          "Matching type properties during complex structures checks"
        ],
        mockCodeBlock: `// Simulating check logic inside Compiler check files
export function verifyTypes(expected, assignedValue) {
  const actual = typeof assignedValue;
  if (expected !== actual) {
    return {
      passed: false,
      message: \`Mismatched Types: Expected "\${expected}", got "\${actual}"\`
    };
  }
  return { passed: true };
}`,
        mockCodeLanguage: "typescript",
        executionFlow: [
          "Scanner selects active node insideparsed records",
          "Evaluates expected type declarations from blueprints",
          "Compares keys properties with actual assigned values",
          "Logs explicit red-underlines to helper if mismatch occurs"
        ]
      };
    }
    if (name.includes("translator") || name.includes("emitter") || name.includes("code")) {
      return {
        longDescription: "The final production translator. Erases TS interface bounds, deletes type parameters metadata, and translates advanced structures to basic vanilla JavaScript arrays pages can parse.",
        analogy: "Like a professional diplomat. They translate an elaborate legal document loaded with complex terms into a simple common language which any civilian can run.",
        whyCritical: "Web browsers cannot parse TypeScript. If the translator outputs malformed JS, the app crashes outright on launch.",
        bestPractices: [
          "Configure compiler options to emit standardized, lightweight Javascript.",
          "Ensure sourcemaps generations are checked to trace client exceptions.",
          "Clean out old unused build directories automatically prior to compiling."
        ],
        commonTasks: [
          "Stripping out TypeScript interfaces and annotations cleanly",
          "Translating advanced features to simple legacy loops",
          "Creating sourcemap coordinates back to TS original lines"
        ],
        mockCodeBlock: `// Input TS:
const scaleValue = (qty: number): number => qty * 1.5;

// Output Compiled JavaScript:
"use strict";
var scaleValue = function (qty) { return qty * 1.5; };`,
        mockCodeLanguage: "javascript",
        executionFlow: [
          "Accepts pristine Abstract Syntax trees from semantic scanner",
          "Locates types annotations and cuts them cleanly",
          "Saves compiled code lines into lightweight JS files",
          "Writes sourcemap JSON strings to assist code tracking"
        ]
      };
    }
    return {
      longDescription: "The editor co-pilot. Runs background system checking algorithms (LSP) that feed autocomplete suggestions, import pointers, and error notifications into your development editor on every stroke.",
      analogy: "A professional co-pilot sitting adjacent to you inside a plane cockpit. They pre-heat throttle pins, read lists, and signal warning lights before any error develops.",
      whyCritical: "Without active LSP checks, coders must run slow manual compiler scripts over-and-over to catch simple spelling typos, grinding speed to a crawl.",
      bestPractices: [
        "Integrate compiler caches on your computer to keep edits fluid.",
        "Set up fast formatting shortcuts to clear common syntactic clutter.",
        "Select plugins matching TypeScript guidelines for clean styling rules."
      ],
      commonTasks: [
        "Supplying dynamic properties autofills as you type",
        "Delivering informative code context on mouse pointers hover",
        "Initiating auto-import lookups for external code folders"
      ],
      mockCodeBlock: `// LSP hover message schema
const hoverMetadata = {
  contents: [
    { language: "typescript", value: "const totalScore: number" },
    "Combines user raw values and calculates average ranges."
  ],
  range: { start: { line: 8, character: 4 }, end: { line: 8, character: 14 } }
};`,
      mockCodeLanguage: "json",
      executionFlow: [
        "Editor reports editor change indicators to background LSP",
        "LSP performs type matching checks on modified lines subset",
        "Updates error list indices and suggestions archives",
        "Transmits popup menus and yellow tags to screen view"
      ]
    };
  }

  // DEFAULT / FALLBACK REPOSITORIES (What most scanned custom repos use!)
  if (name.includes("frontend") || name.includes("interface") || name.includes("display") || name.includes("ui")) {
    return {
      longDescription: "The visual operations center. Built using responsive elements and structured views, this module renders dashboard columns, sets color standards, supports interactive boxes, and manages client react hook states.",
      analogy: "A state-of-the-art visual furniture showroom. It is where everything is polished, illuminated, and beautifully arranged for guests to admire, keeping interactions simple and charming.",
      whyCritical: "Laggy visual rendering or awkward margins immediately trigger a sense of low quality, causing users to abandon the application.",
      bestPractices: [
        "Separate visual layers into isolated, reusable sub-components.",
        "Always use standard, descriptive labels and maintain high-contrast styling.",
        "Employ native animation utilities to emphasize priority updates."
      ],
      commonTasks: [
        "Constructing beautiful and clean layout templates",
        "Managing client-side click parameters and modal screens",
        "Adapting display structures gracefully for mobile use"
      ],
      mockCodeBlock: `// Example of standard UI Component (src/components/MetricCard.tsx)
import React from "react";

export function MetricCard({ label, value, color }) {
  return (
    <div className="p-5 rounded-2xl border border-white/[0.08] bg-white/[0.02] flex flex-col justify-between">
      <span className="text-xs text-gray-500 font-mono uppercase">{label}</span>
      <span className="text-2xl font-black mt-2 text-white">{value}</span>
    </div>
  );
}`,
      mockCodeLanguage: "tsx",
      executionFlow: [
        "Parses layout files and bundles stylesheet classes",
        "Arranges dimensions smoothly to expand on desktop rows",
        "Binds event listeners to user button click targets",
        "Re-renders individual component states on state change triggers"
      ]
    };
  }
  if (name.includes("backend") || name.includes("api") || name.includes("router")) {
    return {
      longDescription: "The operations controller. Operates behind secure endpoints to receive requests, clean input params lists, compute calculations, check session security permissions, and query databases.",
      analogy: "The kitchen inside an active restaurant. The front house points to a menu card, but only internal chefs manage recipes, stoves, and fire, sending out clean meals.",
      whyCritical: "Backend faults cause servers to crash, corrupt transaction pipelines, or fail to authenticate accounts, locking everyone out.",
      bestPractices: [
        "Validate input strings using validators before sending queries.",
        "Limit command request rates to prevent denial-of-service spikes.",
        "Separate development configuration settings into secure environmental scopes."
      ],
      commonTasks: [
        "Configuring security CORS limits and route permissions",
        "Conducting sessions validations and credentials checking",
        "Converting complex queries parameters into API lists"
      ],
      mockCodeBlock: `// Express controller route example (server.ts)
import express from "express";
const router = express.Router();

router.post("/api/submit", async (req, res) => {
  const { email, message } = req.body;
  if (!email || !message) {
    return res.status(400).json({ error: "Required params are missing" });
  }
  const response = await db.saveMessage({ email, message });
  res.status(202).json({ success: true, record: response });
});`,
      mockCodeLanguage: "typescript",
      executionFlow: [
        "Receives parameters packets sent from Frontend",
        "Runs sanitation checks to screen out bad code scripts",
        "Confirms active connection token checks on head requests",
        "Coordinates with data tables and returns lightweight files"
      ]
    };
  }
  if (name.includes("data") || name.includes("database") || name.includes("storage")) {
    return {
      longDescription: "The durable vault layer. Manages persistent file records, enforces table relations, optimizes storage reads, and processes critical transactions safely so information remains intact across database restarts.",
      analogy: "The central library archives storage bank. Every single log item, page, and book is catalogued in numbered storage drawers with backup indices, impervious to outages.",
      whyCritical: "Database failures or corruptions can vaporize customer accounts, erase transaction histories, and destroy critical business logs.",
      bestPractices: [
        "Anchor relational schemas clearly inside tables definitions.",
        "Schedule continuous automated database snapshots securely.",
        "Isolate table columns so queries fetch only required data fields."
      ],
      commonTasks: [
        "Storing primary user records and data sets inside tables",
        "Enforcing table relationships and cascading deletes",
        "Initializing migration changes without resetting files"
      ],
      mockCodeBlock: `// Drizzle Schema declaration (src/db/schema.ts)
import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";

export const savedAnalysis = sqliteTable('saved_analysis', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  repoName: text('repo_name').notNull(),
  summaryText: text('summary_text'),
  addedAt: text('added_at'),
});`,
      mockCodeLanguage: "typescript",
      executionFlow: [
        "Awaits command connection sent from API router",
        "Applies record locks to block dual editing issues",
        "Saves parameters permanent safely on flash disk memory",
        "Issues confirmation code index to verify success"
      ]
    };
  }
  return {
    longDescription: "The communication coordinator. Handles transactional emails, runs event notification hooks, connects SMS streams, and manages async task queues to keep the main thread running at absolute speed.",
    analogy: "Like a prompt shipping port mail coordinator. While other workers load packages onto docks, they address envelopes and speed notifications to clients immediately.",
    whyCritical: "If notification modules fail, users can't receive security passkeys, receipt files drop, and critical system alarms are silent.",
    bestPractices: [
      "Process email dispatches inside separate, async worker threads.",
      "Check recipient mail bounces feedback to prevent spam ratings.",
      "Structure messages within clear responsive HTML blocks."
    ],
    commonTasks: [
      "Transmitting automated reset account passwords emails",
      "Emitting immediate pop-up updates to client browser screens",
      "Managing retry rules for external network API drops"
    ],
    mockCodeBlock: `// Conceptual background notification sender
import { sendEmail } from "./mailer";

export async function queueNotification(userId, message) {
  const contact = await db.getUserContactInfo(userId);
  if (contact.emailAlertsEnabled) {
    await sendEmail({
      to: contact.email,
      subject: "Critical System Alert",
      body: \`<p>\${message}</p>\`
    });
  }
}`,
    mockCodeLanguage: "typescript",
    executionFlow: [
      "Backend events queue registers a success criteria update",
      "Packs matching metrics into pre-made visual template sheets",
      "Dispatches call over external mail/notification API gateway",
      "Monitors retry queues in background to handle system drops"
    ]
  };
}

const iconMap: Record<string, any> = {
  layout: Layout,
  globe: Globe,
  server: Server,
  cpu: Cpu,
  shield: ShieldCheck,
  database: Database,
  zap: Zap,
  folder: Folder,
  terminal: Terminal,
  layers: Layers,
  code: Code,
};

export default function AnalysisDashboard({ repo, isSaved, onSaveToggle, onBackToSearch, onAnalyze, serverAvailable }: AnalysisDashboardProps) {
  const [viewMode, setViewMode] = useState<'overview' | 'modules' | 'analysis'>('overview');
  const [activeTab, setActiveTab] = useState<'architecture' | 'technology' | 'structure'>('architecture');
  const [activeConnectIdx, setActiveConnectIdx] = useState<number | null>(null);
  const [selectedModuleIdx, setSelectedModuleIdx] = useState<number>(0);
  const [hoveredNodeIdx, setHoveredNodeIdx] = useState<number | null>(null);

  const overviewData = getNonTechnicalOverview(repo.fullName);
  const eduMeta = getEducationalMetadata(repo.fullName);
  const architectureData = (repo as Repository & { architecture?: any }).architecture;
  const architectureSummary = architectureData?.architecture_summary || architectureData?.summary || repo.analysis.projectSummary || '';
  const architectureType = architectureData?.architecture_type || 'Unable to confidently determine from repository evidence.';
  const architectureFlow = Array.isArray(architectureData?.flow) && architectureData.flow.length > 0
    ? architectureData.flow
    : eduMeta.requestFlow.map((item) => item.step);
  const requestLifecycle = Array.isArray(architectureData?.request_lifecycle) && architectureData.request_lifecycle.length > 0
    ? architectureData.request_lifecycle
    : eduMeta.requestFlow.map((item) => item.label);
  const componentCards = Array.isArray(architectureData?.components) && architectureData.components.length > 0
    ? architectureData.components
    : [];
  const communicationPatterns = Array.isArray(architectureData?.communication) && architectureData.communication.length > 0
    ? architectureData.communication
    : [];
  const deploymentSummary = architectureData?.deployment || 'Unable to confidently determine from repository evidence.';
  const architectureNodes = architectureFlow.length > 0
    ? architectureFlow.map((step: string, index: number) => ({
      name: step,
      desc: requestLifecycle[index] || 'Repository-derived architecture step',
      icon: index % 2 === 0 ? Layout : Server,
    }))
    : eduMeta.architectureNodes;
  const executiveOverview = repo.overview.executiveOverview || {
    what_is_this_project: [
      repo.overview.aiSummary || `${repo.fullName} is a project designed to help users complete a focused workflow.`,
      repo.description || 'It brings the repository purpose, visible files, and documented capabilities into one organized experience.'
    ],
    why_was_it_built: overviewData.problemSolved,
    user_features: overviewData.simpleFeatures.map((feature) => ({
      name: feature.title,
      description: feature.desc,
    })).slice(0, 8),
    typical_use_cases: [
      'Understanding what the project offers before deciding whether to use it.',
      'Evaluating whether the repository solves a practical need for a team or individual.',
      'Learning how the project can fit into a real workflow.'
    ],
    who_is_this_for: overviewData.whoUsesIt,
    why_is_it_valuable: overviewData.solutionProvided,
    one_line_summary: repo.overview.aiSummary || `${repo.fullName} helps users complete its core workflow in an organized way.`,
  };
  const businessModules = (repo.analysis.businessModules && repo.analysis.businessModules.length > 0)
    ? repo.analysis.businessModules
    : overviewData.coreModules.map((module) => ({
      name: module.name,
      purpose: module.purpose,
      description: module.purpose,
      capabilities: [module.responsibility],
      components: module.keyFilesFolders,
      connected_modules: module.dependencies,
      confidence: 60,
    }));

  const findModuleIndex = (mName: string) => {
    const nameClean = mName.toLowerCase();
    const idx = overviewData.coreModules.findIndex(mod => {
      const modClean = mod.name.toLowerCase();
      return modClean.includes(nameClean) || nameClean.includes(modClean) ||
        modClean.substring(0, 8).includes(nameClean.substring(0, 8)) ||
        nameClean.substring(0, 8).includes(modClean.substring(0, 8));
    });
    return idx !== -1 ? idx : 0;
  };

  const getNodeCoords = (idx: number) => {
    const nodesCount = overviewData.coreModules.length;
    if (nodesCount === 4) {
      if (idx === 0) return { x: 25, y: 24 };
      if (idx === 1) return { x: 75, y: 24 };
      if (idx === 2) return { x: 25, y: 76 };
      if (idx === 3) return { x: 75, y: 76 };
    }
    const angle = (idx * 2 * Math.PI) / nodesCount - Math.PI / 2;
    return {
      x: Math.round(50 + 26 * Math.cos(angle)),
      y: Math.round(50 + 26 * Math.sin(angle))
    };
  };

  const handleNodeClick = (nodeIdx: number) => {
    const activeLink = overviewData.dependencyMap.interactions.findIndex((link) => {
      const fromIdx = findModuleIndex(link.from);
      const toIdx = findModuleIndex(link.to);
      return fromIdx === nodeIdx || toIdx === nodeIdx;
    });
    if (activeLink !== -1) {
      setActiveConnectIdx(activeConnectIdx === activeLink ? null : activeLink);
    }
  };

  function getConnectionInspectorDetails(projectName: string, fromName: string, toName: string) {
    const pName = projectName.toLowerCase();
    const from = fromName.toLowerCase();
    const to = toName.toLowerCase();

    // Next.js
    if (pName.includes("next")) {
      if (from.includes("frontend") && to.includes("router")) {
        return {
          protocol: "Client-Side Transition Router",
          payload: "Route address string path, e.g., '/blog/posts/15'",
          security: "Sanitized on client side, verified target matches",
          benefit: "Instant zero-reload pages navigation"
        };
      }
      if (from.includes("router") && to.includes("optimizer")) {
        return {
          protocol: "Prefetch Chunks (HTTP GET)",
          payload: "HTML document structures, lightweight JS chunks, AVIF images",
          security: "Public CDN assets signed, read-only cache streams",
          benefit: "Preloads pages in static backgrounds before user clicks"
        };
      }
      if (from.includes("frontend") && to.includes("api")) {
        return {
          protocol: "Secure HTTPS / Next Server Actions",
          payload: "Encrypted form payloads, JSON state, Auth cookies",
          security: "TLS secured, token keys run strictly inside Node.js servers",
          benefit: "Runs database actions without venting secret keys to client browser"
        };
      }
    }

    // Supabase
    if (pName.includes("supabase")) {
      if (from.includes("auth") && to.includes("database")) {
        return {
          protocol: "Postgres JWT Claim injection",
          payload: "Signed JSON Web Token (JWT) with secure user account metadata",
          security: "Cryptographic signature assertion mapping verification",
          benefit: "Hooks front-end clicks instantly into secure PostgreSQL Row-Level Security checks"
        };
      }
      if (from.includes("database") && to.includes("broadcast")) {
        return {
          protocol: "Postgres Write-Ahead Logs (WAL) -> WebSockets Client",
          payload: "Row transaction logs delta payload (INSERT/UPDATE/DELETE parameters)",
          security: "Active token sockets filter records to permit only matching client roles",
          benefit: "Feeds updates to chat nodes or dynamic graphs screens instantly without manual re-query"
        };
      }
      if (from.includes("database") && to.includes("storage")) {
        return {
          protocol: "PostgreSQL internal RLS buckets trigger rules",
          payload: "Media bucket directory ID, folder upload ownership check indices",
          security: "Enforces relational permissions on external binary assets pools",
          benefit: "Shields private client files, templates, or invoices from unauthenticated guest scrapers"
        };
      }
    }

    // Kubernetes
    if (pName.includes("kubernetes")) {
      if (from.includes("command") && to.includes("worker")) {
        return {
          protocol: "Secure mTLS gRPC channel (kubelet API socket)",
          payload: "Container pod runtime specifications metadata and health checking rules",
          security: "Mutual TLS cert verification, RBAC permissions verified",
          benefit: "Dynamically spins up replacement containers on host worker engines"
        };
      }
      if (from.includes("worker") && to.includes("auto")) {
        return {
          protocol: "Internal metrics scrapers scraper pool (TCP pull)",
          payload: "Active host CPU usage stats, active memory allocations count",
          security: "Isolate network port bindings, read-only node query scopes",
          benefit: "Exposes system parameters to analyze scaling triggers"
        };
      }
      if (from.includes("auto") && to.includes("command")) {
        return {
          protocol: "HPA (HorizontalPodAutoscaler) scale controller client",
          payload: "Scale delta instruction parameters (+3 / -1 replica counts)",
          security: "Strict RBAC token keys authorized inside centralized API server",
          benefit: "Spawns backup resources to shield apps from heavy cellular surges"
        };
      }
      if (from.includes("traffic") && to.includes("worker")) {
        return {
          protocol: "TCP kube-proxy translation / iptables route rules",
          payload: "Client web query packets streams distributed to active pod ports",
          security: "Continuous readiness checks route callers strictly to completely healthy nodes",
          benefit: "Bypasses slow or crashed servers, sustaining uninterrupted visits"
        };
      }
    }

    // Fallback / Generic Custom repository
    return {
      protocol: "Structured secure API connector / Local Web Bridge",
      payload: "Saves record update state, query filters params, triggers events",
      security: "Parameters sanitized, token authorization verified at gateway",
      benefit: "Sustains database integrity and coordinates browser displays"
    };
  }

  const developerTabs = [
    { id: 'architecture', label: 'Architecture & Flow' },
    { id: 'technology', label: 'Technology Stack' },
    { id: 'structure', label: 'Repository Structure' }
  ] as const;

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10" id="analysis-dashboard">

      {/* Breadcrumbs Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between border-b border-white/[0.08] pb-6 mb-8 gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-gray-500 font-mono">
            <button onClick={onBackToSearch} className="hover:text-white transition-colors cursor-pointer bg-transparent border-0 p-0 text-left">RepoIQ</button>
            <ChevronRight className="h-3 w-3" />
            <span>Analysis</span>
            <ChevronRight className="h-3 w-3" />
            <span className="text-gray-300">{repo.fullName}</span>
          </div>

          <div className="flex flex-wrap items-center gap-3 mt-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white font-sans">
              {repo.fullName}
            </h1>
            <a
              href={repo.url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 text-xs text-purple-300 hover:text-white bg-purple-500/10 hover:bg-[#8B5CF6]/20 border border-[#8B5CF6]/20 rounded-lg px-2.5 py-1.5 transition-all"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              <span>GitHub Link</span>
            </a>
          </div>
          <p className="text-sm text-gray-400 mt-2 max-w-2xl font-sans leading-relaxed">
            {repo.description}
          </p>
        </div>

        {/* Saved Favorites & Share layout buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => onSaveToggle(repo.fullName)}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold flex items-center gap-2 transition-all cursor-pointer ${isSaved
                ? 'bg-[#8B5CF6] text-white shadow-[0_0_15px_rgba(139,92,246,0.3)]'
                : 'bg-white/[0.03] text-gray-300 border border-white/[0.06] hover:bg-white/[0.06]'
              }`}
          >
            <Star className={`h-4.5 w-4.5 ${isSaved ? 'fill-white text-white' : 'text-gray-400'}`} />
            <span>{isSaved ? 'Saved in Library' : 'Save Repository'}</span>
          </button>

          <button
            onClick={() => {
              navigator.clipboard.writeText(window.location.href);
              alert("Copied repository link to clipboard!");
            }}
            className="p-2.5 rounded-xl bg-white/[0.03] text-gray-400 hover:text-white border border-white/[0.06] hover:bg-white/[0.06] transition-all cursor-pointer"
            title="Share Analysis"
          >
            <Share2 className="h-4.5 w-4.5" />
          </button>
        </div>
      </div>

      {/* Mode Perspective Selector (Overview vs Modules vs Technical Deep-Dive) */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 mb-8 bg-white/[0.01] border border-white/[0.05] p-3 rounded-2xl">
        <div className="flex flex-col sm:flex-row bg-black/40 border border-white/[0.08] p-1 rounded-xl w-full lg:w-auto gap-1">
          <button
            onClick={() => setViewMode('overview')}
            className={`flex-1 sm:flex-initial px-5 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${viewMode === 'overview'
                ? 'bg-gradient-to-r from-purple-500/20 to-purple-600/10 text-purple-300 border border-purple-500/30'
                : 'text-gray-400 hover:text-white'
              }`}
          >
            <HelpCircle className="h-4 w-4" />
            <span>📊 Executive Overview</span>
          </button>

          <button
            onClick={() => setViewMode('modules')}
            className={`flex-1 sm:flex-initial px-5 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${viewMode === 'modules'
                ? 'bg-gradient-to-r from-indigo-500/20 to-purple-600/10 text-indigo-300 border border-indigo-500/30'
                : 'text-gray-400 hover:text-white'
              }`}
          >
            <Layers className="h-4 w-4" />
            <span>📦 Core Modules</span>
          </button>

          <button
            onClick={() => setViewMode('analysis')}
            className={`flex-1 sm:flex-initial px-5 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${viewMode === 'analysis'
                ? 'bg-gradient-to-r from-[#8B5CF6]/20 to-purple-600/10 text-white border border-[#8B5CF6]/30'
                : 'text-gray-400 hover:text-white'
              }`}
          >
            <Terminal className="h-4 w-4" />
            <span>💻 Technical Deep-Dive</span>
          </button>
        </div>
      </div>

      {/* -----------------perspective 1: EXECUTIVE OVERVIEW -----------------*/}
      {viewMode === 'overview' && (
        <div className="space-y-8 animate-fade-in" id="executive-overview-frame">
          <div className="rounded-2xl bg-gradient-to-br from-[#8B5CF6]/10 to-transparent border border-[#8B5CF6]/15 p-6 sm:p-8 relative overflow-hidden">
            <div className="absolute top-0 right-0 h-48 w-48 bg-[#8B5CF6]/10 blur-[80px] rounded-full pointer-events-none" />
            <div className="relative">
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-[#8B5CF6] uppercase tracking-wider mb-3">
                <Sparkles className="h-3.5 w-3.5" />
                <span>Executive Overview</span>
              </div>
              <h3 className="text-xl sm:text-2xl font-black text-white tracking-tight font-sans">
                What is this Project?
              </h3>
              <div className="mt-4 space-y-4">
                {executiveOverview.what_is_this_project.slice(0, 3).map((paragraph, idx) => (
                  <p key={idx} className="text-gray-200 text-sm sm:text-base leading-relaxed font-sans">
                    {paragraph}
                  </p>
                ))}
              </div>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">What can Users do?</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {executiveOverview.user_features.slice(0, 8).map((feature, idx) => (
                <div key={idx} className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-5 hover:border-[#8B5CF6]/20 transition-all">
                  <span className="text-[10px] font-mono font-bold text-indigo-400">FEATURE 0{idx + 1}</span>
                  <h5 className="font-bold text-sm text-white mt-1.5">{feature.name}</h5>
                  <p className="text-xs text-gray-400 mt-2 leading-relaxed">{feature.description}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl bg-white/[0.02] border border-white/[0.08] p-6">
              <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Typical Use Cases</h4>
              <div className="space-y-3">
                {executiveOverview.typical_use_cases.map((useCase, idx) => (
                  <div key={idx} className="flex gap-3 rounded-xl bg-black/20 border border-white/[0.04] p-3">
                    <span className="text-xs font-mono text-[#8B5CF6] font-bold">0{idx + 1}</span>
                    <p className="text-xs text-gray-300 leading-relaxed">{useCase}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl bg-white/[0.02] border border-white/[0.08] p-6">
              <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Who is this For?</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {executiveOverview.who_is_this_for.map((audience, idx) => (
                  <div key={idx} className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-4">
                    <span className="text-xs font-mono text-[#8B5CF6] font-bold block mb-1">0{idx + 1}</span>
                    <p className="text-xs font-semibold text-gray-200">{audience}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>
      )}

      {/* -----------------perspective: CORE MODULES BLUEPRINT & INTERACTION GRAPH -----------------*/}
      {viewMode === 'modules' && (
        <div className="space-y-8 animate-fade-in" id="core-modules-frame">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-purple-400 uppercase tracking-wider mb-2">
                <Layers className="h-3.5 w-3.5" />
                <span>Business Module Analyzer</span>
              </div>
              <h3 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                Core Modules
              </h3>
              <p className="text-xs sm:text-sm text-gray-400 max-w-2xl mt-1.5 leading-relaxed">
                Functional building blocks inferred from repository evidence: README, routes, services, file names, structure, and detected technologies.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-gray-400 bg-white/[0.02] border border-white/[0.06] rounded-xl px-3 py-1.5 self-start md:self-auto">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>{businessModules.length} functional modules</span>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5" id="core-modules-grid">
            {businessModules.map((module, idx) => (
              <div
                key={`${module.name}-${idx}`}
                className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-6 hover:border-[#8B5CF6]/30 hover:bg-[#8B5CF6]/[0.01] transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className="text-[10px] font-mono font-bold text-purple-400">MODULE 0{idx + 1}</span>
                    <h4 className="text-lg font-black text-white tracking-tight mt-1">{module.name}</h4>
                  </div>
                  <span className="shrink-0 px-2 py-1 rounded-lg bg-purple-500/10 text-purple-300 border border-purple-500/20 text-[10px] font-mono font-bold">
                    {module.confidence}% confidence
                  </span>
                </div>

                <div className="mt-4">
                  <h5 className="text-xs uppercase tracking-widest text-gray-500 font-mono mb-2">Purpose</h5>
                  <p className="text-sm text-gray-300 leading-relaxed font-sans">
                    {module.purpose || module.description}
                  </p>
                </div>

                <div className="mt-5">
                  <h5 className="text-xs uppercase tracking-widest text-gray-500 font-mono mb-2">Key Capabilities</h5>
                  <div className="flex flex-wrap gap-2">
                    {module.capabilities.length > 0 ? module.capabilities.map((capability, capIdx) => (
                      <span key={capIdx} className="rounded-lg bg-indigo-500/10 text-indigo-200 border border-indigo-500/15 px-2.5 py-1 text-[11px] leading-relaxed">
                        {capability}
                      </span>
                    )) : (
                      <span className="text-xs text-gray-500">No high-confidence capabilities detected.</span>
                    )}
                  </div>
                </div>

                <div className="mt-5">
                  <h5 className="text-xs uppercase tracking-widest text-gray-500 font-mono mb-2">Related Components</h5>
                  <div className="flex flex-wrap gap-2">
                    {module.components.length > 0 ? module.components.map((component, componentIdx) => (
                      <span key={componentIdx} className="rounded-lg bg-white/[0.04] text-gray-300 border border-white/[0.06] px-2.5 py-1 text-[11px] font-mono break-all">
                        {component}
                      </span>
                    )) : (
                      <span className="text-xs text-gray-500">No specific components listed.</span>
                    )}
                  </div>
                </div>

                <div className="mt-5">
                  <h5 className="text-xs uppercase tracking-widest text-gray-500 font-mono mb-2">Connected Modules</h5>
                  <div className="flex flex-wrap gap-2">
                    {module.connected_modules.length > 0 ? module.connected_modules.map((connected, connectedIdx) => (
                      <span key={connectedIdx} className="rounded-lg bg-purple-500/10 text-purple-200 border border-purple-500/15 px-2.5 py-1 text-[11px]">
                        {connected}
                      </span>
                    )) : (
                      <span className="text-xs text-gray-500">No explicit module connections detected.</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {false && viewMode === 'modules' && (
        <div className="space-y-10 animate-fade-in" id="core-modules-frame">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-purple-400 uppercase tracking-wider mb-2">
                <Layers className="h-3.5 w-3.5" />
                <span>Repository Blueprint</span>
              </div>
              <h3 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                Core Modules
              </h3>
              <p className="text-xs sm:text-sm text-gray-400 max-w-2xl mt-1.5 leading-relaxed">
                Understand the primary building blocks of this repository. Learn how they are structured, what responsibilities they hold, and how they interact logistically.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-gray-400 bg-white/[0.02] border border-white/[0.06] rounded-xl px-3 py-1.5 self-start md:self-auto">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Primary Modules Decoded</span>
            </div>
          </div>

          {/* Modules Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5" id="core-modules-grid">
            {overviewData.coreModules.map((module, mIdx) => {
              const IconComponent = iconMap[module.iconName] || Code;
              const isSelected = selectedModuleIdx === mIdx;
              return (
                <button
                  key={mIdx}
                  onClick={() => setSelectedModuleIdx(mIdx)}
                  className={`group relative text-left flex flex-col justify-between rounded-2xl border p-5 transition-all duration-300 overflow-hidden cursor-pointer w-full bg-transparent ${isSelected
                      ? 'border-purple-500 bg-purple-500/[0.04] shadow-[0_0_20px_rgba(139,92,246,0.15)] scale-[1.02]'
                      : 'border-white/[0.08] bg-white/[0.01] hover:border-white/[0.2] hover:bg-white/[0.02]'
                    }`}
                >
                  {/* Corner gradient glow */}
                  <div className={`absolute -right-8 -top-8 h-20 w-20 rounded-full blur-2xl transition-all duration-300 ${isSelected ? 'bg-purple-500/15' : 'bg-purple-500/0 group-hover:bg-purple-500/5'
                    }`} />

                  <div className="w-full text-left">
                    {/* Card Header */}
                    <div className="flex items-start justify-between gap-3 mb-4">
                      <div className={`h-9 w-9 rounded-xl flex items-center justify-center transition-all duration-300 font-bold uppercase tracking-wider ${isSelected
                          ? 'bg-purple-500/20 text-purple-300 scale-110'
                          : 'bg-purple-500/10 text-purple-400 group-hover:scale-110 group-hover:text-purple-300'
                        }`}>
                        <IconComponent className="h-4.5 w-4.5" />
                      </div>
                      <span className="inline-flex items-center text-[10px] font-bold font-mono px-2 py-0.5 rounded-full border bg-white/[0.04] text-gray-400 border-white/[0.08]">
                        UNIT 0{mIdx + 1}
                      </span>
                    </div>

                    {/* Module Info */}
                    <h4 className={`text-sm font-bold mb-2 leading-snug transition-colors ${isSelected ? 'text-purple-300' : 'text-white group-hover:text-purple-300'
                      }`}>
                      {module.name}
                    </h4>
                    <p className="text-xs text-gray-400 leading-relaxed font-sans mb-3 min-h-[48px]">
                      {module.purpose}
                    </p>

                    {/* Responsibility block with quote design */}
                    <div className="text-[11px] text-gray-300 bg-white/[0.02] border-l-2 border-purple-500/40 pl-2.5 py-1 mb-4 leading-normal italic font-sans font-mono">
                      {module.responsibility}
                    </div>
                  </div>

                  {/* Metadata Section */}
                  <div className="pt-3 border-t border-white/[0.04] space-y-2 w-full text-left">
                    <div>
                      <span className="text-[9px] font-mono uppercase tracking-wider text-gray-500 block">KEY ENVIRONMENT</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {module.keyFilesFolders.slice(0, 3).map((file, fIdx) => (
                          <span
                            key={fIdx}
                            className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-gray-300 border border-white/[0.06]"
                          >
                            {file}
                          </span>
                        ))}
                        {module.keyFilesFolders.length > 3 && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.02] text-gray-400 border border-transparent">
                            +{module.keyFilesFolders.length - 3} more
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Module Deep-Dive Workspace (EDUCATIONAL WORKBENCH) */}
          {(() => {
            const selectedModule = overviewData.coreModules[selectedModuleIdx] || overviewData.coreModules[0];
            const spec = getModuleDetailedSpecs(repo.fullName, selectedModule.name);
            const SelectedIconComponent = iconMap[selectedModule.iconName] || Code;

            return (
              <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-6 lg:p-8 relative overflow-hidden space-y-8 animate-fade-in" id="module-deep-dive-panel">
                {/* Visual Accent header lines */}
                <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-purple-500 via-pink-500 to-transparent" />

                {/* Header info */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-white/[0.06]">
                  <div className="flex items-start gap-4">
                    <div className="h-12 w-12 rounded-xl bg-purple-500/20 text-purple-300 flex items-center justify-center font-bold relative shrink-0">
                      <SelectedIconComponent className="h-6 w-6" />
                      <div className="absolute -inset-1 rounded-xl bg-purple-500/10 blur-md -z-10" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[9px] font-mono text-purple-400 uppercase tracking-widest bg-purple-500/10 px-2 py-0.5 rounded">Deep-Dive Workspace</span>
                        <span className="inline-flex items-center text-[10px] font-bold font-mono px-2 py-0.5 rounded-full border bg-purple-500/10 text-purple-300 border-purple-500/20">
                          Active Component
                        </span>
                      </div>
                      <h4 className="text-xl font-black text-white tracking-tight mt-1 font-sans">{selectedModule.name}</h4>
                      <p className="text-xs text-gray-400 mt-1 max-w-2xl font-sans leading-relaxed">{spec.longDescription}</p>
                    </div>
                  </div>

                  {/* Scope metadata pill board */}
                  <div className="flex flex-wrap gap-4 lg:self-center bg-white/[0.01] border border-white/[0.04] p-3.5 rounded-xl">
                    <div>
                      <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">Key Source Tree</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {selectedModule.keyFilesFolders.map((file, fIdx) => (
                          <span key={fIdx} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-white border border-white/[0.06]">{file}</span>
                        ))}
                      </div>
                    </div>
                    <div className="border-l border-white/[0.06] pl-4">
                      <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">Dependencies</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {selectedModule.dependencies.map((dep, dIdx) => (
                          <span key={dIdx} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/15">{dep}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Body panels: Row 1 - Analogy & Critical Failure Mode */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* The Analogy panel */}
                  <div className="rounded-xl border border-white/[0.06] bg-white/[0.01] p-5 space-y-3 relative overflow-hidden">
                    <div className="absolute top-2 right-2 text-white/[0.02]">
                      <BookOpen className="h-24 w-24" />
                    </div>
                    <div className="flex items-center gap-2 text-xs font-bold text-amber-400 font-sans uppercase tracking-wider">
                      <HelpCircle className="h-4 w-4 shrink-0" />
                      <span>Beginner-Friendly Analogy</span>
                    </div>
                    <p className="text-sm text-gray-300 font-sans leading-relaxed italic pr-4">
                      "{spec.analogy}"
                    </p>
                    <div className="text-[10px] text-gray-500 font-sans">
                      *Analogies shield non-engineers from abstract complexity by building familiar mental models.
                    </div>
                  </div>

                  {/* Why it is crucial / failure mode panel */}
                  <div className="rounded-xl border border-white/[0.06] bg-white/[0.01] p-5 space-y-3 relative overflow-hidden">
                    <div className="absolute top-2 right-2 text-white/[0.02]">
                      <AlertCircle className="h-24 w-24" />
                    </div>
                    <div className="flex items-center gap-2 text-xs font-bold text-rose-400 font-sans uppercase tracking-wider">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      <span>Why is this critical? (Failure Mode)</span>
                    </div>
                    <p className="text-xs text-gray-300 font-sans leading-relaxed">
                      {spec.whyCritical}
                    </p>
                    <div className="text-[10px] text-gray-500 font-sans">
                      *Analyzing system failures helps understand boundaries and safety loops built into our codebase.
                    </div>
                  </div>
                </div>

                {/* Body panels: Row 2 - Code Blueprint Draft & Execution Flow Pipeline */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Code blueprint card */}
                  <div className="lg:col-span-7 rounded-xl border border-white/[0.06] bg-[#09090D] overflow-hidden flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.04] bg-white/[0.02]">
                        <div className="flex items-center gap-2">
                          <Code className="h-4 w-4 text-purple-400" />
                          <span className="text-xs font-mono font-bold text-gray-300">Simplified Code Blueprint</span>
                        </div>
                        <span className="text-[10px] font-mono uppercase text-gray-500 px-1.5 py-0.5 rounded bg-white/[0.04]">
                          {spec.mockCodeLanguage}
                        </span>
                      </div>
                      <div className="p-4 overflow-x-auto">
                        <pre className="text-xs font-mono text-gray-300 leading-relaxed max-h-[300px] overflow-y-auto style-scrollbar">
                          <code>{spec.mockCodeBlock}</code>
                        </pre>
                      </div>
                    </div>
                    <div className="px-4 py-2.5 bg-white/[0.01] border-t border-white/[0.04] text-[10px] font-mono text-gray-500 flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                      <span>Conceptual mock implementation details for learning purposes.</span>
                    </div>
                  </div>

                  {/* Execution Flow Pipeline card */}
                  <div className="lg:col-span-5 rounded-xl border border-white/[0.06] bg-white/[0.01] p-5 flex flex-col justify-between space-y-4">
                    <div>
                      <div className="flex items-center gap-2 text-xs font-bold text-purple-400 uppercase tracking-wider mb-4">
                        <Zap className="h-4 w-4 shrink-0" />
                        <span>Dynamic Execution Step Pipeline</span>
                      </div>
                      <div className="relative pl-6 space-y-4 border-l border-white/[0.08] ml-2 font-sans text-xs text-left">
                        {spec.executionFlow.map((step, sIdx) => (
                          <div key={sIdx} className="relative">
                            {/* Bullet Dot */}
                            <div className="absolute -left-[30px] top-[2px] h-4 w-4 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center font-mono text-[9px] font-black border border-purple-500/50">
                              {sIdx + 1}
                            </div>
                            <p className="text-white font-medium">{step}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="text-[10px] text-gray-500 font-mono mt-2 pt-2 border-t border-white/[0.04] text-left">
                      *Follow numbers step-by-step to visualize how data flows dynamically on runtime executions.
                    </div>
                  </div>
                </div>

                {/* Body panels: Row 3 - Good Practices & Common Tasks Side-By-Side lists */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                  {/* Good Architectural Practices */}
                  <div className="space-y-3 text-left">
                    <div className="flex items-center gap-2 text-xs font-bold text-gray-300 uppercase tracking-wider">
                      <Award className="h-4 w-4 text-purple-400 animate-pulse" />
                      <span>Good Architectural Practices</span>
                    </div>
                    <ul className="space-y-2">
                      {spec.bestPractices.map((practice, pIdx) => (
                        <li key={pIdx} className="flex items-start gap-2 text-xs text-gray-400 leading-normal">
                          <span className="text-purple-400 font-bold shrink-0 mt-0.5">▪</span>
                          <span>{practice}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Common Tasks on this Module */}
                  <div className="space-y-3 text-left">
                    <div className="flex items-center gap-2 text-xs font-bold text-gray-300 uppercase tracking-wider">
                      <Terminal className="h-4 w-4 text-purple-400" />
                      <span>Typical Module Responsibilities</span>
                    </div>
                    <ul className="space-y-2">
                      {spec.commonTasks.map((task, tIdx) => (
                        <li key={tIdx} className="flex items-start gap-2 text-xs text-gray-400 leading-normal">
                          <span className="text-purple-400 font-bold shrink-0 mt-0.5">▸</span>
                          <span>{task}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

              </div>
            );
          })()}

          {/* Simplified Dependency Map Component */}
          <div className="rounded-2xl border border-purple-500/15 bg-[#0A0A0E] p-5 sm:p-7 relative overflow-hidden mt-6">
            <div className="absolute top-0 right-0 h-40 w-40 bg-purple-500/[0.02] blur-2xl rounded-full pointer-events-none" />

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

              {/* Left Side: Relationship explanations and interactions list */}
              <div className="lg:col-span-5 space-y-4">
                <div>
                  <span className="text-[9px] font-mono text-purple-400 uppercase tracking-widest block mb-1.5 animate-pulse">Simplified Data Flows</span>
                  <h4 className="text-base font-extrabold text-white font-sans">Module Interaction Map</h4>
                  <p className="text-xs text-gray-400 leading-relaxed mt-1 font-sans">
                    {overviewData.dependencyMap.description}
                  </p>
                </div>

                <div className="space-y-2">
                  <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">Interactive Connections (Click to trace flow)</span>
                  <div className="flex flex-col gap-2">
                    {overviewData.dependencyMap.interactions.map((link, idx) => {
                      const isSelected = activeConnectIdx === idx;
                      return (
                        <button
                          key={idx}
                          onClick={() => setActiveConnectIdx(activeConnectIdx === idx ? null : idx)}
                          className={`w-full text-left p-3 rounded-xl border transition-all duration-300 cursor-pointer ${isSelected
                              ? 'bg-purple-500/10 border-purple-500/40 hover:bg-purple-500/15 shadow-[0_0_15px_rgba(139,92,246,0.1)]'
                              : 'bg-white/[0.01] border-white/[0.06] hover:bg-white/[0.03] hover:border-white/[0.12]'
                            }`}
                        >
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-xs font-bold text-white flex items-center gap-1.5 font-sans">
                              <span className={`h-1.5 w-1.5 rounded-full ${isSelected ? 'bg-purple-400 animate-ping' : 'bg-gray-500'}`} />
                              {link.from}
                            </span>
                            <span className="text-[10px] font-mono text-purple-400">&rarr;</span>
                            <span className="text-xs font-bold text-gray-300 font-sans">{link.to}</span>
                          </div>
                          <p className="text-[11px] text-gray-400 leading-normal pl-3 font-sans">
                            {link.flowDesc}
                          </p>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Secure Flow Inspector Details Component */}
                {activeConnectIdx !== null ? (() => {
                  const activeLink = overviewData.dependencyMap.interactions[activeConnectIdx];
                  const inspectorDetails = getConnectionInspectorDetails(overviewData.projectName, activeLink.from, activeLink.to);
                  return (
                    <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20 animate-fade-in text-left space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-medium font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30 uppercase tracking-wider">Telemetry Active</span>
                        <span className="text-[9px] font-mono text-gray-500">Node Handshake Details</span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-sans">
                        <div className="space-y-0.5">
                          <span className="text-gray-500 font-mono text-[9px] uppercase block">Flow Protocol</span>
                          <span className="text-white font-semibold leading-tight block">{inspectorDetails.protocol}</span>
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-gray-500 font-mono text-[9px] uppercase block">Data Footprint</span>
                          <span className="text-purple-300 font-mono text-[11px] leading-tight block break-words">{inspectorDetails.payload}</span>
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-gray-500 font-mono text-[9px] uppercase block">Security / Enforcer</span>
                          <span className="text-emerald-400 font-semibold flex items-center gap-1 leading-tight">
                            <ShieldCheck className="h-3.5 w-3.5 shrink-0" /> {inspectorDetails.security}
                          </span>
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-gray-500 font-mono text-[9px] uppercase block">Process Benefit</span>
                          <span className="text-gray-300 italic leading-tight block">{inspectorDetails.benefit}</span>
                        </div>
                      </div>
                    </div>
                  );
                })() : (
                  <div className="p-4 rounded-xl bg-white/[0.01] border border-white/[0.04] text-center">
                    <span className="text-xs text-gray-500 font-sans">💡 Hover or click any flow track connection to trigger live telemetry metrics inspections</span>
                  </div>
                )}
              </div>

              {/* Right Side: Beautiful interactive visual graph node model */}
              <div className="lg:col-span-7 bg-black/40 rounded-2xl border border-white/[0.05] p-5 lg:p-7 flex flex-col justify-center min-h-[360px] relative w-full overflow-hidden">
                <span className="text-[9px] font-mono text-gray-500 uppercase tracking-widest block text-center mb-6">Interactive Pipeline Topology</span>

                <div className="grid grid-cols-2 gap-x-8 gap-y-12 max-w-lg mx-auto relative p-6 w-full">

                  {/* Render visual cards nodes */}
                  {overviewData.coreModules.map((module, idx) => {
                    const IconComponent = iconMap[module.iconName] || Code;

                    // Check if module is connected in selected link
                    let isSource = false;
                    let isTarget = false;
                    let isAnyActive = activeConnectIdx !== null;

                    if (activeConnectIdx !== null) {
                      const activeLink = overviewData.dependencyMap.interactions[activeConnectIdx];
                      const srcIdx = findModuleIndex(activeLink.from);
                      const dstIdx = findModuleIndex(activeLink.to);
                      isSource = srcIdx === idx;
                      isTarget = dstIdx === idx;
                    }

                    return (
                      <button
                        key={idx}
                        onClick={() => handleNodeClick(idx)}
                        onMouseEnter={() => setHoveredNodeIdx(idx)}
                        onMouseLeave={() => setHoveredNodeIdx(null)}
                        className={`flex flex-col items-center p-4 rounded-xl border text-center transition-all duration-500 relative z-10 w-full cursor-pointer select-none group ${isSource
                            ? 'bg-purple-500/15 border-purple-400 shadow-[0_0_25px_rgba(139,92,246,0.25)] scale-[1.04]'
                            : isTarget
                              ? 'bg-purple-500/10 border-indigo-400 shadow-[0_0_25px_rgba(99,102,241,0.25)] scale-[1.04]'
                              : hoveredNodeIdx === idx
                                ? 'bg-white/[0.04] border-white/[0.2] scale-[1.02]'
                                : isAnyActive
                                  ? 'opacity-40 bg-transparent border-white/[0.03]'
                                  : 'bg-[#0E0E12] border-white/[0.08] hover:border-white/[0.15]'
                          }`}
                      >
                        {/* Sockets */}
                        <div className="absolute top-1/2 -left-1.5 h-3 w-3 rounded-full border border-white/[0.15] bg-[#0A0A0E] flex items-center justify-center -translate-y-1/2">
                          <span className={`h-1.5 w-1.5 rounded-full ${isSource || isTarget ? 'bg-purple-400' : 'bg-gray-700'}`} />
                        </div>
                        <div className="absolute top-1/2 -right-1.5 h-3 w-3 rounded-full border border-white/[0.15] bg-[#0A0A0E] flex items-center justify-center -translate-y-1/2">
                          <span className={`h-1.5 w-1.5 rounded-full ${isSource || isTarget ? 'bg-purple-400' : 'bg-gray-700'}`} />
                        </div>

                        {/* Top decorative bar */}
                        <div className="w-full flex items-center justify-between text-[8px] font-mono text-gray-500 mb-2 pb-1.5 border-b border-white/[0.03]">
                          <span className="tracking-wider uppercase">UNIT_0{idx + 1}</span>
                          <span className="flex items-center gap-1">
                            <span className={`h-1 w-1 rounded-full ${isSource || isTarget ? 'bg-purple-400 animate-ping' : 'bg-emerald-500'}`} />
                            ACTIVE
                          </span>
                        </div>

                        {/* Centered Graphic Icon */}
                        <div className={`h-9 w-9 rounded-xl flex items-center justify-center mb-2.5 transition-all duration-500 ${isSource || isTarget
                            ? 'bg-purple-500/25 text-purple-200'
                            : 'bg-white/[0.03] text-gray-400 group-hover:text-white group-hover:bg-white/[0.07]'
                          }`}>
                          <IconComponent className="h-4.5 w-4.5" />
                        </div>

                        <span className="text-[11px] font-extrabold text-white font-mono leading-tight group-hover:text-purple-300 transition-colors">
                          {module.name}
                        </span>

                        <span className="text-[9px] font-mono text-emerald-500 mt-1 uppercase tracking-tight">
                          ONLINE
                        </span>

                        {/* Bottom alignment badges */}
                        {isSource && (
                          <span className="absolute -bottom-2.5 bg-gradient-to-r from-purple-500 to-indigo-500 text-white text-[8px] font-mono font-bold px-2 py-0.5 rounded uppercase tracking-widest scale-90 shadow-md">Source Node</span>
                        )}
                        {isTarget && (
                          <span className="absolute -bottom-2.5 bg-gradient-to-r from-indigo-500 to-purple-500 text-white text-[8px] font-mono font-bold px-2 py-0.5 rounded uppercase tracking-widest scale-90 shadow-md">Receiver Node</span>
                        )}
                      </button>
                    );
                  })}

                  {/* Curving overlay connect vectors map */}
                  <div className="absolute inset-0 pointer-events-none z-0">
                    <svg className="w-full h-full text-white/[0.04]" viewBox="0 0 100 100" preserveAspectRatio="none">
                      <defs>
                        <marker id="arrow-active" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#c084fc" />
                        </marker>
                        <marker id="arrow-inactive" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="rgba(255,255,255,0.15)" />
                        </marker>
                      </defs>

                      {overviewData.dependencyMap.interactions.map((link, idx) => {
                        const fromIdx = findModuleIndex(link.from);
                        const toIdx = findModuleIndex(link.to);
                        const fromCoords = getNodeCoords(fromIdx);
                        const toCoords = getNodeCoords(toIdx);
                        const isActive = activeConnectIdx === idx;
                        const isHovered = hoveredNodeIdx === fromIdx || hoveredNodeIdx === toIdx;

                        const dx = toCoords.x - fromCoords.x;
                        const dy = toCoords.y - fromCoords.y;
                        const midX = (fromCoords.x + toCoords.x) / 2;
                        const midY = (fromCoords.y + toCoords.y) / 2;
                        const len = Math.sqrt(dx * dx + dy * dy) || 1;

                        // Perpendicular curve sag offsets
                        const pullX = midX - (dy / len) * 5;
                        const pullY = midY + (dx / len) * 5;

                        const pathD = `M ${fromCoords.x} ${fromCoords.y} Q ${pullX} ${pullY} ${toCoords.x} ${toCoords.y}`;

                        return (
                          <g key={idx}>
                            {/* Glowing shadow base */}
                            <path
                              d={pathD}
                              fill="none"
                              stroke={isActive ? "rgba(167, 139, 250, 0.2)" : isHovered ? "rgba(255,255,255,0.05)" : "transparent"}
                              strokeWidth={isActive ? "6" : "3"}
                              className="transition-all duration-300"
                            />
                            {/* Core connection track string */}
                            <path
                              d={pathD}
                              fill="none"
                              stroke={isActive ? "#a78bfa" : "rgba(255, 255, 255, 0.08)"}
                              strokeWidth={isActive ? "2" : "1.2"}
                              strokeDasharray={isActive ? "none" : "5,5"}
                              markerEnd={`url(#${isActive ? 'arrow-active' : 'arrow-inactive'})`}
                              className="transition-all duration-300"
                            />
                            {/* Animated stream pulse dots */}
                            {isActive && (
                              <>
                                <path
                                  d={pathD}
                                  fill="none"
                                  stroke="#c084fc"
                                  strokeWidth="2"
                                  className="animate-stream-active opacity-90"
                                />
                                <circle r="2" fill="#c084fc" className="shadow-[0_0_8px_#c084fc]">
                                  <animateMotion dur="1.8s" repeatCount="indefinite" path={pathD} />
                                </circle>
                              </>
                            )}
                          </g>
                        );
                      })}
                    </svg>
                  </div>

                </div>

                <div className="mt-8 text-center text-[10px] font-mono text-gray-500">
                  {activeConnectIdx !== null ? (
                    <span className="flex items-center justify-center gap-1.5 text-[#8B5CF6] font-semibold animate-pulse">
                      <Zap className="h-3.5 w-3.5 animate-bounce" /> Click another pipeline node or track connection to inspect telemetry details
                    </span>
                  ) : (
                    <span>Click any pipeline module node or correlation connection track to visualize live data flows</span>
                  )}
                </div>
              </div>

            </div>
          </div>
        </div>
      )}

      {/* -----------------perspective 2: DEVELOPER ADVANCED ANALYSIS HUB -----------------*/}
      {viewMode === 'analysis' && (
        <div className="space-y-8 animate-fade-in" id="developer-analysis-frame">

          {/* Sub-navigation tabs inside Developer Hub */}
          <div className="border-b border-white/[0.08] mb-6">
            <div className="flex space-x-1 sm:space-x-4 overflow-x-auto pb-px scrollbar-none">
              {developerTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-3 rounded-lg text-xs font-semibold transition-all duration-200 cursor-pointer shrink-0 whitespace-nowrap ${activeTab === tab.id
                      ? 'text-white bg-white/[0.05] border border-white/[0.08] shadow-sm'
                      : 'text-gray-400 hover:text-white hover:bg-white/[0.01]'
                    }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Rendering the Active developer sub-tab */}
          <div className="mt-4">

            {/* SUB-TAB 1: ARCHITECTURE & REQUEST FLOW */}
            {activeTab === 'architecture' && (
              <div className="space-y-8" id="dev-tab-architecture">

                {/* Visual Architecture Diagram card */}
                <div className="rounded-2xl bg-white/[0.02] border border-white/[0.08] p-6 sm:p-8">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <span className="text-xs font-mono text-gray-500 uppercase tracking-widest block">Architecture Summary</span>
                      <p className="text-sm text-gray-300 leading-relaxed">{architectureSummary || 'Architecture details will appear once the backend analysis completes.'}</p>
                    </div>
                    <div className="rounded-xl border border-[#8B5CF6]/20 bg-[#8B5CF6]/10 px-4 py-3 w-full max-w-xs">
                      <div className="text-[10px] font-mono uppercase tracking-widest text-[#c4b5fd]">Inferred Type</div>
                      <div className="mt-1 text-sm font-semibold text-white">{architectureType}</div>
                    </div>
                  </div>

                {/* Modular Architecture Visualization — derived from detected tech stack */}
                {(() => {
                  // Resolve tech stack items from rawStack.categories or analysis.techStack
                  const categories = (repo as any).rawStack?.categories;
                  const ts = repo.analysis.techStack;

                  const getTechNames = (items: any[] | undefined): string[] => {
                    if (!Array.isArray(items)) return [];
                    const names: string[] = [];
                    for (const item of items) {
                      const name = typeof item === 'string' ? item : item?.name;
                      if (name && typeof name === 'string' && !names.includes(name)) {
                        names.push(name);
                      }
                    }
                    return names.slice(0, 8);
                  };

                  const frontendItems = getTechNames(categories?.frontend ?? ts?.frontend);
                  const backendItems = getTechNames(categories?.backend ?? ts?.backend);
                  const databaseItems = getTechNames(categories?.database ?? ts?.database);
                  const infraItems = getTechNames([
                    ...(categories?.infrastructure ?? ts?.infrastructure ?? []),
                    ...(categories?.devops ?? ts?.devops ?? []),
                    ...(categories?.cloud ?? ts?.cloud ?? []),
                  ]);

                  const moduleDefs = [
                    {
                      label: 'Frontend',
                      icon: Layout,
                      color: 'from-blue-500/10 via-blue-500/5 to-transparent',
                      border: 'border-blue-500/20 hover:border-blue-500/40',
                      badgeBg: 'bg-blue-500/10 text-blue-300 border-blue-500/25',
                      accent: 'text-blue-400',
                      items: frontendItems
                    },
                    {
                      label: 'Backend',
                      icon: Server,
                      color: 'from-purple-500/10 via-purple-500/5 to-transparent',
                      border: 'border-purple-500/20 hover:border-purple-500/40',
                      badgeBg: 'bg-purple-500/10 text-purple-300 border-purple-500/25',
                      accent: 'text-purple-400',
                      items: backendItems
                    },
                    {
                      label: 'Database',
                      icon: Database,
                      color: 'from-emerald-500/10 via-emerald-500/5 to-transparent',
                      border: 'border-emerald-500/20 hover:border-emerald-500/40',
                      badgeBg: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/25',
                      accent: 'text-emerald-400',
                      items: databaseItems
                    },
                    {
                      label: 'Infrastructure',
                      icon: Layers,
                      color: 'from-amber-500/10 via-amber-500/5 to-transparent',
                      border: 'border-amber-500/20 hover:border-amber-500/40',
                      badgeBg: 'bg-amber-500/10 text-amber-300 border-amber-500/25',
                      accent: 'text-amber-400',
                      items: infraItems
                    },
                  ].filter(m => m.items.length > 0);

                  if (moduleDefs.length === 0) {
                    return (
                      <div className="mt-8 rounded-2xl border border-white/[0.08] bg-white/[0.01] p-6 text-sm text-gray-400 text-center font-sans">
                        No technology stack data detected for this repository yet.
                      </div>
                    );
                  }

                  return (
                    <div className="mt-8 pt-4 border-t border-white/[0.06]">
                      {/* Architecture Hierarchy Header */}
                      <div className="flex flex-col items-center">
                        {/* Root: Repository node */}
                        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-[#8B5CF6]/30 bg-[#8B5CF6]/10 text-sm font-semibold text-white font-mono shadow-sm">
                          <Globe className="h-4 w-4 text-[#8B5CF6]" />
                          <span>{repo.name || repo.fullName}</span>
                        </div>

                        {/* Downward Connector with Arrow */}
                        <div className="flex flex-col items-center my-2">
                          <div className="w-px h-5 bg-[#8B5CF6]/40" />
                          <div className="px-2.5 py-0.5 rounded-full border border-white/[0.08] bg-black/60 text-[10px] font-mono uppercase tracking-widest text-gray-400">
                            Architecture Modules
                          </div>
                          <div className="w-px h-5 bg-[#8B5CF6]/40" />
                          <ChevronDown className="h-4 w-4 text-[#8B5CF6]/60 -mt-1" />
                        </div>
                      </div>

                      {/* Modular Columns: Clean High-Level Representation */}
                      <div className={`mt-4 grid gap-4 ${
                        moduleDefs.length === 4
                          ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4'
                          : moduleDefs.length === 3
                            ? 'grid-cols-1 sm:grid-cols-3'
                            : 'grid-cols-1 sm:grid-cols-2'
                      }`}>
                        {moduleDefs.map((mod) => {
                          const ModIcon = mod.icon;
                          return (
                            <div
                              key={mod.label}
                              className={`rounded-2xl border ${mod.border} bg-gradient-to-b ${mod.color} p-5 flex flex-col justify-between transition-colors shadow-sm`}
                            >
                              <div>
                                {/* Module Tier Header */}
                                <div className="flex items-center justify-between gap-2 mb-3.5">
                                  <div className="flex items-center gap-2">
                                    <div className="h-7 w-7 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center">
                                      <ModIcon className={`h-4 w-4 ${mod.accent}`} />
                                    </div>
                                    <span className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                                      {mod.label}
                                    </span>
                                  </div>
                                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${mod.badgeBg}`}>
                                    {mod.items.length} {mod.items.length === 1 ? 'tech' : 'techs'}
                                  </span>
                                </div>

                                {/* Technology Tags */}
                                <div className="flex flex-wrap gap-1.5 mt-2">
                                  {mod.items.map((tech, tIdx) => (
                                    <span
                                      key={tIdx}
                                      className="rounded-lg border border-white/[0.06] bg-black/40 px-2.5 py-1 text-xs text-gray-200 font-sans font-medium"
                                    >
                                      {tech}
                                    </span>
                                  ))}
                                </div>
                              </div>

                              <div className="mt-4 pt-3 border-t border-white/[0.04] flex items-center justify-between text-[10px] font-mono text-gray-500">
                                <span>Detected layer</span>
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()}
                </div>


                {/* Structured Request Flow Walkthrough */}
                <div>
                  <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Incremental Request Flow</h4>
                  <div className="rounded-2xl bg-white/[0.01] border border-white/[0.05] p-5 sm:p-6 space-y-4 relative">
                    <div className="absolute left-8 top-10 bottom-10 w-px bg-[#8B5CF6]/20 hidden sm:block" />
                    {(architectureData?.flow?.length ? architectureFlow : eduMeta.requestFlow.map((f) => f.step)).map((step, i) => (
                      <div key={`${step}-${i}`} className="flex gap-4 items-center relative z-10">
                        <span className="h-6.5 w-6.5 rounded-full bg-purple-950 border border-[#8B5CF6]/40 text-[#8B5CF6] flex items-center justify-center text-xs font-mono shrink-0 font-bold">
                          {i + 1}
                        </span>
                        <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4 bg-black/40 border border-white/[0.04] rounded-xl p-3.5 hover:bg-white/[0.02] hover:border-white/[0.08] transition-all">
                          <span className="font-bold text-xs text-[#8B5CF6] uppercase tracking-wider font-mono">{step}</span>
                          <span className="text-xs text-gray-300 sm:col-span-2 font-mono leading-normal">
                            {requestLifecycle[i] || (architectureData?.flow?.length ? 'Unable to confidently determine from repository evidence.' : eduMeta.requestFlow[i]?.label || '')}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Core Code Modules */}
                <div>
                  <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Core Software Modules Mapping</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {componentCards.length > 0 ? componentCards.map((c, i) => (
                      <div key={`${c.name}-${i}`} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 hover:bg-white/[0.04] hover:border-[#8B5CF6]/25 transition-all">
                        <span className="font-bold text-xs text-white block font-mono truncate">{c.name}</span>
                        <div className="mt-4 space-y-3 text-xs text-gray-300 font-sans">
                          <div>
                            <div className="font-semibold text-white text-[10px] uppercase tracking-wider">Purpose</div>
                            <div className="mt-1 leading-snug">{c.purpose || c.responsibility || 'Unable to confidently determine from repository evidence.'}</div>
                          </div>
                          <div>
                            <div className="font-semibold text-white text-[10px] uppercase tracking-wider">Input</div>
                            <div className="mt-1 leading-snug">{c.input || 'Unable to confidently determine from repository evidence.'}</div>
                          </div>
                          <div>
                            <div className="font-semibold text-white text-[10px] uppercase tracking-wider">Output</div>
                            <div className="mt-1 leading-snug">{c.output || 'Unable to confidently determine from repository evidence.'}</div>
                          </div>
                          <div>
                            <div className="font-semibold text-white text-[10px] uppercase tracking-wider">Communicates With</div>
                            <div className="mt-1 leading-snug text-[#c4b5fd]">
                              {(c.communicates_with || c.connected_to || ['Unable to confidently determine from repository evidence.']).join(', ')}
                            </div>
                          </div>
                        </div>
                      </div>
                    )) : eduMeta.coreComponents.map((c, i) => (
                      <div key={i} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 hover:bg-white/[0.04] hover:border-[#8B5CF6]/25 transition-all">
                        <span className="font-bold text-xs text-white block font-mono">{c.title}</span>
                        <p className="text-xs text-gray-400 mt-2.5 leading-relaxed font-sans">{c.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {(architectureData?.sync_path?.length || architectureData?.async_path?.length) && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {architectureData?.sync_path?.length > 0 && (
                      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                        <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Synchronous Path</h4>
                        <div className="space-y-3 text-sm text-gray-300">
                          {architectureData.sync_path.map((step: string, index: number) => (
                            <div key={`${step}-${index}`} className="rounded-xl border border-white/[0.06] bg-black/30 px-4 py-3">
                              {step}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {architectureData?.async_path?.length > 0 && (
                      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                        <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Asynchronous Path</h4>
                        <div className="space-y-3 text-sm text-gray-300">
                          {architectureData.async_path.map((step: string, index: number) => (
                            <div key={`${step}-${index}`} className="rounded-xl border border-white/[0.06] bg-black/30 px-4 py-3">
                              {step}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                    <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Communication Patterns</h4>
                    <div className="space-y-3">
                      {(communicationPatterns.length > 0 ? communicationPatterns : ['Unable to confidently determine from repository evidence.']).map((item, index) => (
                        <div key={`${item}-${index}`} className="rounded-xl border border-white/[0.06] bg-black/30 px-4 py-3 text-sm text-gray-300">
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-5">
                    <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Deployment Overview</h4>
                    <div className="rounded-xl border border-[#8B5CF6]/20 bg-[#8B5CF6]/10 px-4 py-4 text-sm text-gray-200">
                      {deploymentSummary}
                    </div>
                  </div>
                </div>

              </div>
            )}

            {/* SUB-TAB 2: TECHNOLOGY STACK */}
            {activeTab === 'technology' && (
              <div className="space-y-8" id="dev-tab-technology">
                {/* RAW STACK DEBUG */}
                <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6">
                  <h4 className="text-xs font-mono text-red-300 uppercase tracking-widest mb-4">RAW STACK DATA (DEBUG)</h4>
                  <pre className="text-xs text-gray-300 overflow-auto max-h-96 bg-black/50 p-4 rounded-xl">
                    {JSON.stringify((repo as any).rawStack, null, 2)}
                  </pre>
                </div>

                {/* LANGUAGES SECTION */}
                <div>
                  <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Detected Languages</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                    {(repo.languages && repo.languages.length > 0) ? (
                      repo.languages.map((lang, idx) => (
                        <div key={idx} className="rounded-xl bg-white/[0.02] border border-white/[0.06] px-3 py-2">
                          <div className="font-medium text-gray-200 text-sm">{lang}</div>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-gray-400 col-span-full">No languages detected yet.</p>
                    )}
                  </div>
                </div>

                {/* TECHNOLOGIES SECTION */}
                <div>
                  <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-4">Detected Technology Stack</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {(() => {
                      // First check if rawStack.categories exists, otherwise use repo.analysis.techStack
                      const categories = (repo as any).rawStack?.categories;
                      let sections;
                      if (categories) {
                        sections = [
                          { title: 'Frontend', items: categories.frontend },
                          { title: 'Backend', items: categories.backend },
                          { title: 'Database', items: categories.database },
                          { title: 'Infrastructure', items: categories.infrastructure },
                          { title: 'DevOps', items: categories.devops },
                          ...(categories.cloud?.length ? [{ title: 'Cloud', items: categories.cloud }] : []),
                          ...(categories.messaging?.length ? [{ title: 'Messaging', items: categories.messaging }] : []),
                          ...(categories.monitoring?.length ? [{ title: 'Monitoring', items: categories.monitoring }] : []),
                          ...(categories.cicd?.length ? [{ title: 'CI/CD', items: categories.cicd }] : []),
                          ...(categories.tooling?.length ? [{ title: 'Tooling', items: categories.tooling }] : []),
                        ];
                      } else {
                        // Fallback to original structure
                        sections = [
                          { title: 'Frontend', items: repo.analysis.techStack.frontend },
                          { title: 'Backend', items: repo.analysis.techStack.backend },
                          { title: 'Database', items: repo.analysis.techStack.database },
                          { title: 'Infrastructure', items: repo.analysis.techStack.infrastructure },
                          { title: 'DevOps', items: repo.analysis.techStack.devops },
                          ...(repo.analysis.techStack.cloud?.length ? [{ title: 'Cloud', items: repo.analysis.techStack.cloud }] : []),
                          ...(repo.analysis.techStack.messaging?.length ? [{ title: 'Messaging', items: repo.analysis.techStack.messaging }] : []),
                          ...(repo.analysis.techStack.monitoring?.length ? [{ title: 'Monitoring', items: repo.analysis.techStack.monitoring }] : []),
                          ...(repo.analysis.techStack.cicd?.length ? [{ title: 'CI/CD', items: repo.analysis.techStack.cicd }] : []),
                          ...(repo.analysis.techStack.tooling?.length ? [{ title: 'Tooling', items: repo.analysis.techStack.tooling }] : []),
                        ];
                      }
                      return sections.map((section) => (
                        <div key={section.title} className="rounded-2xl border border-white/[0.08] bg-white/[0.01] p-6">
                          <h5 className="text-xs uppercase tracking-widest text-gray-500 font-mono mb-3">{section.title}</h5>
                          {section.items.length > 0 ? (
                            <div className="space-y-3">
                              {section.items.map((item, idx) => (
                                <div key={idx} className="rounded-xl bg-white/[0.02] border border-white/[0.06] px-4 py-3">
                                  {typeof item === "string" ? (
                                    <div className="font-medium text-gray-200">{item}</div>
                                  ) : (
                                    <>
                                      <div className="font-medium text-gray-200">{item.name}</div>
                                      <div className="text-xs text-gray-400 mt-1.5">
                                        Found in {item.count ?? item.sources?.length ?? 1} {(item.count ?? item.sources?.length ?? 1) === 1 ? 'file' : 'files'}
                                      </div>
                                      {Array.isArray(item.sources) && item.sources.length > 0 ? (
                                        <details className="mt-3 text-xs text-gray-400">
                                          <summary className="cursor-pointer text-gray-300">Evidence</summary>
                                          <ul className="mt-2 space-y-1 max-h-40 overflow-auto pr-1">
                                            {item.sources.map((source, sourceIdx) => (
                                              <li key={sourceIdx} className="font-mono text-[11px] text-gray-400 break-all">
                                                {source}
                                              </li>
                                            ))}
                                          </ul>
                                        </details>
                                      ) : (
                                        <div className="text-xs text-gray-400 mt-2 break-all">{item.source}</div>
                                      )}
                                    </>
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-gray-400">No detected {section.title.toLowerCase()} technologies.</p>
                          )}
                        </div>
                      ));
                    })()}
                  </div>
                </div>
              </div>
            )}

            {/* SUB-TAB 3: REPOSITORY STRUCTURE */}
            {activeTab === 'structure' && (
              <div className="space-y-8" id="dev-tab-structure">
                <div>
                  <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                    <div>
                      <h4 className="text-xs font-mono text-gray-500 uppercase tracking-widest">Repository Structure</h4>
                      <p className="text-[10px] text-gray-400 mt-0.5">Browse the cloned repository tree. Expand folders to inspect actual files and directories.</p>
                    </div>
                    <span className="text-[11px] font-mono text-gray-500 bg-black/40 px-3 py-1 rounded-lg border border-white/[0.05]">
                      Root: / {repo.folderStructure.length > 0 ? repo.folderStructure[0].children?.length ?? 0 : 0} top entries
                    </span>
                  </div>

                  <div className="rounded-2xl border border-white/[0.08] bg-black/50 p-4 sm:p-6 outline-none font-sans">
                    {repo.folderStructure.length > 0 ? (
                      repo.folderStructure.map((node, index) => (
                        <FolderTree key={index} node={node} depth={0} />
                      ))
                    ) : (
                      <div className="rounded-2xl border border-dashed border-white/[0.08] bg-white/[0.01] p-6 text-center text-sm text-gray-400">
                        No repository structure available yet.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}


          </div>

        </div>
      )}

    </div>
  );
}
