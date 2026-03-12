import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";

interface LogCardTitleProps {
  title: string;
  summary: string;
  highlights: string[];
}

export function LogCardTitle({ title, summary, highlights }: LogCardTitleProps) {
  return (
    <HoverCard>
      <h3 className="text-sm font-semibold">
        <HoverCardTrigger asChild>
          <button
            type="button"
            className="inline-flex cursor-help items-center rounded-sm underline decoration-dotted underline-offset-4 transition-colors hover:text-primary focus-visible:text-primary focus-visible:outline-hidden"
          >
            {title}
          </button>
        </HoverCardTrigger>
      </h3>
      <HoverCardContent className="space-y-3">
        <div className="space-y-1">
          <p className="text-[11px] font-medium tracking-[0.18em] text-primary/80 uppercase">
            业务说明
          </p>
          <p className="text-sm font-semibold">{title}</p>
        </div>
        <p className="text-sm leading-6 text-foreground/85">{summary}</p>
        <ul className="space-y-2 text-xs leading-5 text-muted-foreground">
          {highlights.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary/70" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </HoverCardContent>
    </HoverCard>
  );
}
