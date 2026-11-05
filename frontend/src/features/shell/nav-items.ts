import {
  BarChart3,
  Bot,
  Flame,
  HelpCircle,
  Timer,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  tag: string;
  /** Shown in the mobile bottom bar; the rest live in the drawer. */
  primary: boolean;
  /** Hidden unless the signed-in account is an admin. Cosmetic only --
   *  the route and the API both check the role themselves. */
  adminOnly?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { name: "Feed", href: "/feed", icon: Flame, tag: "Learn", primary: true },
  { name: "Quiz", href: "/quiz", icon: HelpCircle, tag: "Practice", primary: true },
  { name: "Test", href: "/test", icon: Timer, tag: "Mock", primary: true },
  { name: "Analytics", href: "/analytics", icon: BarChart3, tag: "Stats", primary: true },
  { name: "Agent", href: "/agent", icon: Bot, tag: "Ask", primary: false },
  { name: "Users", href: "/admin", icon: Users, tag: "Admin", primary: false,
    adminOnly: true },
];

/** The items to show for a given role. Called by both navigations, so
 *  the admin link cannot appear in one and not the other. */
export const navItemsFor = (role: string | undefined): NavItem[] =>
  NAV_ITEMS.filter((item) => !item.adminOnly || role === "admin");

export const isActivePath = (pathname: string, href: string): boolean =>
  pathname === href || (href === "/feed" && pathname === "/");
