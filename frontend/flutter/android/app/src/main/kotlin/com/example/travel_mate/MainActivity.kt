package com.example.travel_mate

import android.os.Bundle
import android.util.Log
import com.navercorp.nid.NidOAuth
import com.navercorp.nid.core.data.datastore.NidOAuthInitializingCallback
import com.navercorp.nid.core.data.errorcode.NidOAuthErrorCode
import com.navercorp.nid.oauth.util.NidOAuthCallback
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterFragmentActivity() {
    private var pendingNaverResult: MethodChannel.Result? = null
    private var naverReady = false
    private var naverInitializing = true
    private var naverInitError: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        Log.d(TAG, "NAVER init start")
        try {
            NidOAuth.initialize(
                applicationContext,
                BuildConfig.NAVER_CLIENT_ID,
                BuildConfig.NAVER_CLIENT_SECRET,
                BuildConfig.NAVER_CLIENT_NAME,
                object : NidOAuthInitializingCallback {
                    override fun onSuccess() {
                        naverReady = true
                        naverInitializing = false
                        naverInitError = null
                        Log.d(TAG, "NAVER init success")
                    }

                    override fun onFailure(e: Exception) {
                        naverReady = false
                        naverInitializing = false
                        naverInitError = e.javaClass.simpleName
                        Log.d(TAG, "NAVER init failure")
                    }
                },
            )
        } catch (e: Exception) {
            naverReady = false
            naverInitializing = false
            naverInitError = e.javaClass.simpleName
            Log.d(TAG, "NAVER init failure")
        }
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "travelmate/naver_auth")
            .setMethodCallHandler { call, result ->
                if (call.method != "login") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                if (pendingNaverResult != null) {
                    result.error("NAVER_LOGIN_IN_PROGRESS", "Naver login is already in progress.", null)
                    return@setMethodCallHandler
                }
                if (naverInitializing) {
                    result.error(
                        "NAVER_SDK_INITIALIZING",
                        "Naver login is initializing. Please try again shortly.",
                        null,
                    )
                    return@setMethodCallHandler
                }
                if (!naverReady) {
                    result.error(
                        "NAVER_SDK_INITIALIZATION_FAILED",
                        "Naver login could not be initialized.",
                        naverInitError,
                    )
                    return@setMethodCallHandler
                }

                pendingNaverResult = result
                try {
                    Log.d(TAG, "NAVER login requested")
                    NidOAuth.requestLogin(
                        this@MainActivity,
                        object : NidOAuthCallback {
                            override fun onSuccess() {
                                Log.d(TAG, "NAVER login success")

                                val pendingResult = pendingNaverResult
                                val accessToken = NidOAuth.getAccessToken()
                                if (accessToken.isNullOrBlank()) {
                                    pendingResult?.error(
                                        "NAVER_ACCESS_TOKEN_MISSING",
                                        "Naver access token is missing.",
                                        null,
                                    )
                                } else {
                                    pendingResult?.success(accessToken)
                                }
                                pendingNaverResult = null
                            }

                            override fun onFailure(errorCode: String, errorDesc: String) {
                                Log.d(TAG, "NAVER login failure code: $errorCode")

                                val code = if (errorCode == NidOAuthErrorCode.CLIENT_USER_CANCEL.code) {
                                    "NAVER_LOGIN_CANCELLED"
                                } else {
                                    "NAVER_LOGIN_FAILED"
                                }
                                val message = if (code == "NAVER_LOGIN_CANCELLED") {
                                    "Naver login was cancelled."
                                } else {
                                    "Naver login failed."
                                }
                                pendingNaverResult?.error(code, message, errorDesc)
                                pendingNaverResult = null
                            }
                        },
                    )
                } catch (e: Exception) {
                    if (pendingNaverResult === result) {
                        pendingNaverResult = null
                        val errorCode = e.javaClass.simpleName
                        Log.d(TAG, "NAVER login failure code: $errorCode")
                        result.error("NAVER_LOGIN_FAILED", "Naver login failed.", errorCode)
                    }
                }
            }
    }

    private companion object {
        const val TAG = "TravelMateNaver"
    }
}
