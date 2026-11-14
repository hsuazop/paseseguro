const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

(async () => {
  const root = path.resolve(__dirname, '..');
  const tools = JSON.parse(fs.readFileSync(path.join(root, 'outputs/android-tools.json'), 'utf8').replace(/^\uFEFF/, ''));
  const env = { ...process.env, JAVA_HOME: tools.JdkDirectory, ANDROID_HOME: tools.SdkDirectory, ANDROID_SDK_ROOT: tools.SdkDirectory };
  const pathKey = Object.keys(env).find(key => key.toLowerCase() === 'path') || 'Path';
  env[pathKey] = path.join(tools.JdkDirectory, 'bin') + ';' + env[pathKey];
  const manager = path.join(tools.CommandLineDirectory, 'bin/sdkmanager.bat');
  const run = args => new Promise((resolve, reject) => {
    const child = spawn(process.env.ComSpec || 'cmd.exe', ['/d', '/c', manager, '--sdk_root=' + tools.SdkDirectory, ...args], { env, windowsHide: true });
    child.stdout.pipe(process.stdout);
    child.stderr.pipe(process.stderr);
    child.on('error', reject);
    child.on('exit', code => code === 0 ? resolve() : reject(new Error('sdkmanager exited with code ' + code)));
    child.stdin.on('error', () => {});
    child.stdin.end('y\n'.repeat(200));
  });
  await run(['--licenses']);
  await run(['--install', 'platform-tools']);
  await new Promise((resolve, reject) => {
    const child = spawn('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', path.join(root, 'scripts/install-android-buildtools.ps1')], { env, windowsHide: true, stdio: 'inherit' });
    child.on('error', reject);
    child.on('exit', code => code === 0 ? resolve() : reject(new Error('Build tools installation failed.')));
  });
  if (!fs.existsSync(path.join(tools.SdkDirectory, 'build-tools/36.1.0/zipalign.exe'))) throw new Error('Android build tools were not installed.');
  console.log('Android tools installed. Gradle installs the required platform during the build.');
})().catch(error => { console.error(error); process.exitCode = 1; });
