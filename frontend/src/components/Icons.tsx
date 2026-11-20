// Small line icons (24px grid, stroke = currentColor)
type P = { size?: number };

const Svg = ({ size = 18, children }: P & { children: React.ReactNode }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

export const SearchIcon = (p: P) => (
  <Svg {...p}><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></Svg>
);
export const TableIcon = (p: P) => (
  <Svg {...p}><rect x="3.5" y="4.5" width="17" height="15" rx="2" /><path d="M3.5 9.5h17M9.5 9.5v10" /></Svg>
);
export const LinkIcon = (p: P) => (
  <Svg {...p}><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></Svg>
);
export const TagIcon = (p: P) => (
  <Svg {...p}><path d="M3.5 12.5V4.5h8l9 9-8 8z" /><circle cx="8" cy="9" r="1.3" /></Svg>
);
export const DatabaseIcon = (p: P) => (
  <Svg {...p}><ellipse cx="12" cy="6" rx="7.5" ry="2.8" /><path d="M4.5 6v12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8V6" /><path d="M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8" /></Svg>
);
export const LockIcon = (p: P) => (
  <Svg {...p}><rect x="5" y="10.5" width="14" height="10" rx="2" /><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" /></Svg>
);
export const SendIcon = (p: P) => (
  <Svg {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Svg>
);
export const ChipIcon = (p: P) => (
  <Svg {...p}><rect x="6.5" y="6.5" width="11" height="11" rx="1.5" /><path d="M9.5 3v3.5M14.5 3v3.5M9.5 17.5V21M14.5 17.5V21M3 9.5h3.5M3 14.5h3.5M17.5 9.5H21M17.5 14.5H21" /></Svg>
);
export const CloudIcon = (p: P) => (
  <Svg {...p}><path d="M7 18.5h10a4 4 0 0 0 .6-8 5.5 5.5 0 0 0-10.7-1A4.5 4.5 0 0 0 7 18.5z" /></Svg>
);
export const ColumnsIcon = (p: P) => (
  <Svg {...p}><rect x="3.5" y="4.5" width="17" height="15" rx="2" /><path d="M12 4.5v15" /></Svg>
);
export const SunIcon = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" /></Svg>
);
export const MoonIcon = (p: P) => (
  <Svg {...p}><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></Svg>
);
export const ShieldIcon = (p: P) => (
  <Svg {...p}><path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z" /></Svg>
);
export const HelpIcon = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="8.5" /><path d="M9.6 9.5a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.8" /><path d="M12 17.2v.1" /></Svg>
);
export const CheckIcon = (p: P) => (
  <Svg {...p}><path d="m5 12.5 4.5 4.5L19 7.5" /></Svg>
);
export const AlertIcon = (p: P) => (
  <Svg {...p}><path d="M12 4 2.8 19.5h18.4z" /><path d="M12 10v4.5M12 17.2v.1" /></Svg>
);
export const ClockIcon = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></Svg>
);
export const XIcon = (p: P) => (
  <Svg {...p}><path d="M6.5 6.5l11 11M17.5 6.5l-11 11" /></Svg>
);
export const ListIcon = (p: P) => (
  <Svg {...p}><path d="M9 6.5h11M9 12h11M9 17.5h11" /><circle cx="4.5" cy="6.5" r="1" /><circle cx="4.5" cy="12" r="1" /><circle cx="4.5" cy="17.5" r="1" /></Svg>
);
export const GraphIcon = (p: P) => (
  <Svg {...p}><rect x="3" y="3.5" width="7" height="5" rx="1.2" /><rect x="14" y="3.5" width="7" height="5" rx="1.2" /><rect x="8.5" y="15.5" width="7" height="5" rx="1.2" /><path d="M6.5 8.5v3h11v-3M12 11.5v4" /></Svg>
);
export const ChatIcon = (p: P) => (
  <Svg {...p}><path d="M4.5 5.5h15v10h-9l-4 3.5v-3.5h-2z" /></Svg>
);
export const BulbIcon = (p: P) => (
  <Svg {...p}><path d="M9 17.5h6M10 20.5h4" /><path d="M12 3.5a5.5 5.5 0 0 0-3.3 9.9c.6.5.8 1.1.8 1.8v.3h5v-.3c0-.7.2-1.3.8-1.8A5.5 5.5 0 0 0 12 3.5z" /></Svg>
);
export const AgentIcon = (p: P) => (
  <Svg {...p}><rect x="5" y="8" width="14" height="11" rx="3" /><path d="M12 4.5V8M9.5 13h.1M14.5 13h.1M9.5 16.2h5" /><circle cx="12" cy="4" r="1" /></Svg>
);
export const LayersIcon = (p: P) => (
  <Svg {...p}><path d="m12 4 8.5 4.5L12 13 3.5 8.5z" /><path d="m3.5 12.5 8.5 4.5 8.5-4.5" /></Svg>
);
export const ArrowIcon = (p: P) => (
  <Svg {...p}><path d="M9 6l6 6-6 6" /></Svg>
);
export const ArrowRightIcon = (p: P) => (
  <Svg {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Svg>
);
export const SpinnerIcon =({ size = 18 }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className="spin" aria-hidden="true">
    <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeOpacity="0.2" strokeWidth="2.2" />
    <path d="M20.5 12a8.5 8.5 0 0 0-8.5-8.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
  </svg>
);

export function ToolIcon({ tool, size }: { tool: string; size?: number }) {
  switch (tool.toLowerCase().replace(/ /g, "_")) {
    case "search_schema":
    case "user_proxy":
      return <SearchIcon size={size} />;
    case "describe_table":
      return <TableIcon size={size} />;
    case "find_join_path":
      return <LinkIcon size={size} />;
    case "find_values":
      return <TagIcon size={size} />;
    default:
      return <DatabaseIcon size={size} />;
  }
}

export function GroupIcon({ group, size }: { group: string; size?: number }) {
  if (group.startsWith("Safety")) return <ShieldIcon size={size} />;
  if (group.startsWith("Trick")) return <HelpIcon size={size} />;
  return <SearchIcon size={size} />;
}
