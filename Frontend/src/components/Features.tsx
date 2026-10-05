import { Search, Brain, Cpu, Layers } from 'lucide-react';

export default function Features() {
  const cards = [
    {
      icon: Search,
      title: "Smart Repository Search",
      description: "Search repositories using natural human ideas instead of exact keywords. Find 'AI chatbots with local database' instantly, mapping concepts to active open-source projects.",
      accent: "from-blue-500 to-purple-500",
      badge: "Semantic Parser"
    },
    {
      icon: Brain,
      title: "AI Project Analysis",
      description: "Instantly compile a developer-facing roadmap summarizing why the codebase exists, how systems communicate internally, core layout maps, and architectural flows.",
      accent: "from-[#8B5CF6] to-pink-500",
      badge: "Deep Reasoning"
    },
    {
      icon: Cpu,
      title: "Tech Stack Detection",
      description: "No need to scan packages manually. RepoIQ isolates frontend elements, backend routes, database drivers, cluster infrastructure, and devops setup with total accuracy.",
      accent: "from-pink-500 to-amber-500",
      badge: "Dependency Inspector"
    },
    {
      icon: Layers,
      title: "Similar Repo Discovery",
      description: "Compare frameworks, evaluate alternative packages, and discover equivalent tooling instantly. Choose the healthiest, most compatible library for your software requirements.",
      accent: "from-teal-500 to-emerald-500",
      badge: "Comparison Engine"
    }
  ];

  return (
    <div className="mx-auto max-w-7xl px-6 lg:px-8 py-20 border-t border-white/[0.05]" id="features-section">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-base font-semibold leading-7 text-[#8B5CF6] font-mono uppercase tracking-wider">
          Platform Architecture
        </h2>
        <p className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl font-sans">
          Engineered for Deep Code Intelligence
        </p>
        <p className="mt-4 text-base text-gray-400 font-sans">
          Stop digging through complex nested index files. Get immediate, production-ready operational metrics instantly.
        </p>
      </div>

      <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
        <dl className="grid max-w-xl grid-cols-1 gap-x-8 gap-y-10 lg:max-w-none lg:grid-cols-4 sm:grid-cols-2">
          {cards.map((card, index) => {
            const Icon = card.icon;
            return (
              <div
                key={index}
                className="group relative flex flex-col justify-between rounded-2xl bg-white/[0.02] border border-white/[0.08] hover:border-[#8B5CF6]/30 hover:bg-[#8B5CF6]/[0.02] p-6 transition-all duration-300 shadow-[0_4px_30px_rgba(0,0,0,0.2)] hover:shadow-[0_4px_30px_rgba(139,92,246,0.15)] overflow-hidden"
              >
                {/* Accent glow corner */}
                <div className={`absolute top-0 right-0 h-40 w-40 -mr-20 -mt-20 rounded-full bg-gradient-to-br ${card.accent} opacity-0 group-hover:opacity-10 blur-2xl transition-opacity duration-500`} />

                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/[0.04] border border-white/[0.08] group-hover:bg-[#8B5CF6]/10 group-hover:border-[#8B5CF6]/30 text-[#8B5CF6] transition-colors duration-300">
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="text-[10px] font-mono font-medium tracking-wider text-purple-300/60 bg-white/[0.03] px-2 py-1 rounded border border-white/[0.04]">
                      {card.badge}
                    </span>
                  </div>

                  <dt className="mt-6 text-lg font-bold tracking-tight text-white font-sans">
                    {card.title}
                  </dt>
                  <dd className="mt-2 text-sm leading-relaxed text-gray-400 font-sans">
                    {card.description}
                  </dd>
                </div>

                <div className="mt-6 pt-4 border-t border-white/[0.04] flex items-center justify-between text-xs font-mono text-gray-500 group-hover:text-white transition-colors">
                  <span>Interactive module</span>
                  <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
                </div>
              </div>
            );
          })}
        </dl>
      </div>
    </div>
  );
}
