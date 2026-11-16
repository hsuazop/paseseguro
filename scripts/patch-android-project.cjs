const fs = require('node:fs');
const path = require('node:path');

module.exports = function patchAndroidProject(project) {
  const manifestFile = path.join(project, 'app/src/main/AndroidManifest.xml');
  let manifest = fs.readFileSync(manifestFile, 'utf8');
  if (!manifest.includes('android.permission.VIBRATE')) {
    manifest = manifest.replace('<application', '<uses-permission android:name="android.permission.VIBRATE"/>\n    <application');
    fs.writeFileSync(manifestFile, manifest);
  }
  fs.copyFileSync(path.join(__dirname, 'android/DelegationService.java'),
    path.join(project, 'app/src/main/java/com/paseseguro/app/DelegationService.java'));
  const registered = /<activity\b[^>]*android:name="com\.google\.androidbrowserhelper\.trusted\.ManageDataLauncherActivity"/.test(manifest);
  if (registered) return false;
  // Android Browser Helper 2.7.4 changes this component's enabled state on every
  // launch, including when the optional settings shortcut is disabled. Keeping
  // the component declared also makes its class name visible to the R8 keep rules.
  const component = `
        <!-- Required by Android Browser Helper even with settings shortcut disabled. -->
        <activity
            android:name="com.google.androidbrowserhelper.trusted.ManageDataLauncherActivity"
            android:enabled="false"
            android:exported="false"
            android:excludeFromRecents="true">
            <meta-data
                android:name="android.support.customtabs.trusted.MANAGE_SPACE_URL"
                android:value="@string/launchUrl" />
        </activity>
`;
  if (!manifest.includes('</application>')) throw new Error('Missing application element in Android manifest.');
  fs.writeFileSync(manifestFile, manifest.replace('</application>', component + '\n    </application>'));
  return true;
};
