package in.co.aflix.shoematchai;

import android.os.Bundle;
import androidx.activity.EdgeToEdge;
// import androidx.core.splashscreen.SplashScreen;
import com.getcapacitor.BridgeActivity;
import android.graphics.Color;
import androidx.core.view.WindowInsetsControllerCompat;

public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // SplashScreen.installSplashScreen(this);
        EdgeToEdge.enable(this);
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.BLACK);
        new WindowInsetsControllerCompat(getWindow(), getWindow().getDecorView())
                .setAppearanceLightStatusBars(false);
    }
}
