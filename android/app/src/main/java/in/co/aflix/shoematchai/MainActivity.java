package in.co.aflix.shoematchai;

import android.os.Bundle;
import androidx.activity.EdgeToEdge;
import androidx.core.splashscreen.SplashScreen;
import com.getcapacitor.BridgeActivity;
import android.graphics.Color;
import androidx.core.view.WindowInsetsControllerCompat;

public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // Must come first: the manifest's launch theme (AppTheme.NoActionBarLaunch)
        // inherits from Theme.SplashScreen expecting this call to drive it. Without
        // it, the OS's own splash-icon view has no dismiss hook wired to this
        // activity's content and can stay stuck on-screen (as a stray icon fragment)
        // once edge-to-edge changes how/when the first frame is reported drawn.
        // Order matches Google's edge-to-edge + splash-screen
        // migration guide: installSplashScreen() -> enableEdgeToEdge() -> super.onCreate().
        SplashScreen.installSplashScreen(this);
        EdgeToEdge.enable(this);
        super.onCreate(savedInstanceState);
        // No-op on Android 15+ (edge-to-edge enforced, bar is always
        // transparent), but keeps the bar black on older OS versions too.
        getWindow().setStatusBarColor(Color.BLACK);
        // Light/white icons for contrast against the black bar — the web
        // side paints the actual black background (see _app.tsx).
        new WindowInsetsControllerCompat(getWindow(), getWindow().getDecorView())
                .setAppearanceLightStatusBars(false);
    }
}
