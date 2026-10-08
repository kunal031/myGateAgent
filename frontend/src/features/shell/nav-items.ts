import {
  BarChart3,
  Bot,
  Flame,
  HelpCircle,
  Timer,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  tag: string;
  /** Shown in the mobile bottom bar; the rest live in the drawer. */
  primary: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { name: "Feed", href: "/feed", icon: Flame, tag: "Recall", primary: true },
  { name: "Quiz", href: "/quiz", icon: HelpCircle, tag: "Drill", primary: true },
  { name: "Test", href: "/test", icon: Timer, tag: "Mock", primary: true },
  { name: "Analytics", href: "/analytics", icon: BarChart3, tag: "Stats", primary: true },
  { name: "Agent", href: "/agent", icon: Bot, tag: "RAG", primary: false },
];

export const isActivePath = (pathname: string, href: string): boolean =>
  pathname === href || (href === "/feed" && pathname === "/");
