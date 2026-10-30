'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity,
  UploadCloud,
  MessageSquareText,
  Users,
  Store,
  Cpu,
  GitFork,
  UserCog,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import BrandMark from './BrandMark';

type NavItem = { label: string; href: string; glyph: string };
const WORKSPACE: NavItem[] = [
  { label: 'Model results', href: '/', glyph: 'overview' },
  { label: 'Upload & analyze', href: '/reviews/submit', glyph: 'batch' },
  { label: 'Products & history', href: '/products', glyph: 'products' },
  { label: 'Review records', href: '/reviews', glyph: 'reviews' },
  { label: 'Review feedback', href: '/feedback', glyph: 'audit' },
  { label: 'Model comparison', href: '/benchmarks', glyph: 'models' },
  { label: 'Example investigation', href: '/examples', glyph: 'graph' },
];
const ADMIN: NavItem[] = [
  { label: 'Reviewer catalog', href: '/reviewers', glyph: 'reviewers' },
  { label: 'Model registry', href: '/models', glyph: 'models' },
  { label: 'User administration', href: '/admin/users', glyph: 'users' },
  { label: 'Audit operations', href: '/admin/audit', glyph: 'audit' },
];

function Glyph({ name, active }: { name: string; active?: boolean }) {
  const iconProps = {
    className: `nav-glyph transition-colors ${active ? 'text-[#0b514a]' : 'text-[#1e2927]/75'}`,
    strokeWidth: 1.75,
  };
  switch (name) {
    case 'overview':
      return <Activity {...iconProps} />;
    case 'batch':
      return <UploadCloud {...iconProps} />;
    case 'reviews':
      return <MessageSquareText {...iconProps} />;
    case 'reviewers':
      return <Users {...iconProps} />;
    case 'products':
    case 'restaurants':
      return <Store {...iconProps} />;
    case 'models':
      return <Cpu {...iconProps} />;
    case 'graph':
      return <GitFork {...iconProps} />;
    case 'users':
      return <UserCog {...iconProps} />;
    case 'audit':
      return <ShieldCheck {...iconProps} />;
    default:
      return <Activity {...iconProps} />;
  }
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  return <Link href={item.href} className={`nav-link ${active ? 'nav-link-active' : ''}`}><Glyph name={item.glyph} active={active}/><span>{item.label}</span></Link>;
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout, isAdmin, isLoading } = useAuth();
  const pathname = usePathname();
  const active = (href: string) => href === '/' || href === '/reviews' ? pathname === href : pathname.startsWith(href);

  // Administration section requires verified ADMIN role and completed auth check
  const isVerifiedAdmin = !isLoading && Boolean(isAdmin && user?.role_key?.trim().toUpperCase() === 'ADMIN');

  return <div className="workspace-shell">
    <aside className="workspace-sidebar">
      <Link href="/" className="brand-lockup"><BrandMark className="brand-symbol"/><span><strong>NeuroGraph</strong><small>REVIEW INTELLIGENCE</small></span></Link>
      <nav className="workspace-nav" aria-label="Workspace navigation">
        <p className="nav-section-label">Workspace</p>{WORKSPACE.map(item => <NavLink key={item.href} item={item} active={active(item.href)}/>)}
        {isVerifiedAdmin && <><p className="nav-section-label nav-admin-label">Administration</p>{ADMIN.map(item => <NavLink key={item.href} item={item} active={active(item.href)}/>)}</>}
      </nav>
      <div className="sidebar-account">{user && <><div className="account-row"><div className="account-monogram">{(user.username || user.email || 'U').slice(0, 1).toUpperCase()}</div><div className="account-copy"><strong>{user.username || user.email}</strong><span>{user.role_key}</span></div></div><button className="signout-button" onClick={logout}>Sign out</button></>}</div>
    </aside>
    <main className="workspace-main"><div className="workspace-content">{children}</div></main>
  </div>;
}
