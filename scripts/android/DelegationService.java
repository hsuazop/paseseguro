package com.paseseguro.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.os.Build;
import java.util.Locale;

/** SOS delivery retains the browser-helper caller authentication and user controls. */
public class DelegationService extends com.google.androidbrowserhelper.trusted.DelegationService {
    private void prepareChannel(String name) {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager manager = getSystemService(NotificationManager.class);
        // Same channel naming convention as AndroidX TrustedWebActivityService.
        String id = name.toLowerCase(Locale.ROOT).replace(' ', '_') + "_channel_id";
        if (manager.getNotificationChannel(id) != null) return;
        NotificationChannel channel = new NotificationChannel(id, "Emergencias SOS", NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription("Alertas de residentes para guardias de la misma residencial");
        channel.enableVibration(true);
        channel.setVibrationPattern(new long[]{0, 500, 200, 500, 200, 800});
        channel.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
        manager.createNotificationChannel(channel);
    }

    @Override
    public boolean onAreNotificationsEnabled(String name) {
        prepareChannel(name);
        return super.onAreNotificationsEnabled(name);
    }

    @Override
    public boolean onNotifyNotificationWithChannel(String tag, int id, Notification notification, String name) {
        prepareChannel(name);
        if (Build.VERSION.SDK_INT < 26) {
            notification.vibrate = new long[]{0, 500, 200, 500, 200, 800};
            notification.priority = Notification.PRIORITY_HIGH;
        }
        return super.onNotifyNotificationWithChannel(tag, id, notification, name);
    }
}
