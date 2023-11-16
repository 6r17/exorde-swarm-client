import { useLocation } from 'preact-iso';
import exordeLogo from '../assets/exorde.svg';

interface HeaderProps {
    connected: boolean
}

function getTrueKeys(inputDict: Record<string, boolean>): string {
  const trueKeys: string[] = [];

  for (const key in inputDict) {
    if (inputDict.hasOwnProperty(key) && inputDict[key] === true) {
      trueKeys.push(key);
    }
  }

  return trueKeys.join(' ');
}

export function Header(props: HeaderProps) {
	const { url } = useLocation();

	return (
		<header>
            <a class="logo" href="https://exorde.network/">
                <img src={exordeLogo} alt="Exorde logo" height="20" width="20" style="margin-top: 6px;" />
            </a>
			<nav>
                <a href="/" class={url == '/' && 'active'}>
					home
				</a>
                <a href="/state" class={url == '/state' && 'active'}>
					state
				</a>
                <a href="/system" class={getTrueKeys({
                            'active': url === '/system',
                            'online': props.connected,
                            'offline': !props.connected
                        })
                    }>
					system
				</a>
			</nav>
		</header>
	);
}
