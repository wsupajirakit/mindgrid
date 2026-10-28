import { createFileRoute } from '@tanstack/react-router'
import { SignInPage } from '../features/auth/components/SignInPage.tsx'

export const Route = createFileRoute('/login')({ component: SignInPage })
