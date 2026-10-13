import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/layout/app_responsive.dart';
import '../../core/theme/app_theme.dart';
import 'analyzing_screen.dart';

/// 홈은 간단한 촬영 진입 화면, 직접 입력은 앨범 이미지 선택 화면을 제공합니다.
class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key, this.galleryOnly = false});

  final bool galleryOnly;

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> {
  final _picker = ImagePicker();
  XFile? _selectedImage;
  bool _picking = false;
  bool _cameraFailed = false;

  Future<void> _pickGalleryImage() async {
    setState(() => _picking = true);
    try {
      final image = await _picker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 85,
        maxWidth: 1600,
      );
      if (image != null && mounted) setState(() => _selectedImage = image);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('사진을 불러오지 못했어요. 권한을 확인해 주세요.')),
        );
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  @override
  void initState() {
    super.initState();
    if (!widget.galleryOnly) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _takePhoto());
    }
  }

  /// 휴대폰 카메라를 열고, 찍은 사진으로 장소 분석을 시작합니다.
  /// 촬영을 취소하면 이전 화면으로 돌아갑니다.
  Future<void> _takePhoto() async {
    setState(() {
      _picking = true;
      _cameraFailed = false;
    });
    try {
      final image = await _picker.pickImage(
        source: ImageSource.camera,
        imageQuality: 85,
        maxWidth: 1600,
      );
      if (!mounted) return;
      if (image == null) {
        Navigator.of(context).maybePop();
        return;
      }
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => AnalyzingScreen(imagePath: image.path),
        ),
      );
    } catch (error) {
      debugPrint('[Camera] open failed: $error');
      if (mounted) {
        setState(() {
          _picking = false;
          _cameraFailed = true;
        });
      }
    }
  }

  void _analyzeImage() {
    final image = _selectedImage;
    if (image == null) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => AnalyzingScreen(imagePath: image.path)),
    );
  }

  /// 카메라 앱이 열리는 동안, 또는 열지 못했을 때 보이는 뷰파인더 화면입니다.
  /// 셔터를 누르면 휴대폰 카메라를 다시 엽니다.
  Widget _buildCaptureScreen(BuildContext context) => Scaffold(
    backgroundColor: Colors.black,
    body: SafeArea(
      child: Stack(
        children: [
          Positioned(
            top: 8,
            left: 8,
            child: IconButton(
              onPressed: () => Navigator.of(context).maybePop(),
              icon: const Icon(Icons.close, color: Colors.white),
              tooltip: '닫기',
            ),
          ),
          const Positioned(
            top: 18,
            right: 22,
            child: Row(
              children: [
                Icon(Icons.flash_off_outlined, color: Colors.white, size: 25),
                SizedBox(width: 22),
                Text(
                  '1×',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                SizedBox(width: 22),
                Icon(
                  Icons.auto_awesome_outlined,
                  color: Colors.white,
                  size: 24,
                ),
              ],
            ),
          ),
          Positioned(
            top: 88,
            left: 30,
            right: 30,
            bottom: 214,
            child: Container(
              decoration: BoxDecoration(
                border: Border.all(color: Colors.white, width: 2),
                borderRadius: BorderRadius.circular(24),
              ),
              alignment: Alignment.center,
              padding: const EdgeInsets.symmetric(horizontal: 28),
              child: _cameraFailed
                  ? const Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.no_photography_outlined,
                          color: Colors.white,
                          size: 56,
                        ),
                        SizedBox(height: 16),
                        Text(
                          '카메라를 열지 못했어요.\n설정에서 카메라 권한을 허용한 뒤 아래 버튼을 눌러주세요.',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    )
                  : Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (_picking) ...[
                          const CircularProgressIndicator(color: Colors.white),
                          const SizedBox(height: 16),
                        ],
                        Text(
                          _picking ? '카메라를 여는 중이에요' : '사진 속 여행지를 화면 중앙에 맞춰주세요',
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 133,
            child: Center(
              child: _cameraFailed
                  ? FilledButton.icon(
                      onPressed: _picking ? null : _takePhoto,
                      icon: const Icon(Icons.photo_camera_outlined),
                      label: const Text(
                        '다시 열기',
                        style: TextStyle(fontSize: 17),
                      ),
                      style: FilledButton.styleFrom(
                        minimumSize: const Size(160, 52),
                      ),
                    )
                  : const DecoratedBox(
                      decoration: BoxDecoration(
                        color: Color(0xFF383838),
                        borderRadius: BorderRadius.all(Radius.circular(26)),
                      ),
                      child: Padding(
                        padding: EdgeInsets.symmetric(
                          horizontal: 20,
                          vertical: 10,
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              '0.6',
                              style: TextStyle(
                                color: Color(0xFFCFCFCF),
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            SizedBox(width: 22),
                            Text(
                              '1×',
                              style: TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                            SizedBox(width: 22),
                            Text(
                              '2',
                              style: TextStyle(
                                color: Color(0xFFCFCFCF),
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
            ),
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 28,
            child: Center(
              child: Semantics(
                button: true,
                label: '사진 촬영하기',
                child: GestureDetector(
                  onTap: _picking ? null : _takePhoto,
                  child: Container(
                    width: 82,
                    height: 82,
                    decoration: BoxDecoration(
                      color: _picking ? const Color(0xFF9E9E9E) : Colors.white,
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: const Color(0xFFBDBDBD),
                        width: 2,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    ),
  );

  Widget _buildGalleryScreen(BuildContext context) => Scaffold(
    backgroundColor: const Color(0xFFF7F8FF),
    body: SafeArea(
      child: Column(
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: IconButton(
              onPressed: () => Navigator.of(context).maybePop(),
              icon: const Icon(Icons.close, color: AppColors.ink),
              tooltip: '닫기',
            ),
          ),
          Expanded(
            child: ListView(
              padding: EdgeInsets.fromLTRB(
                ResponsiveLayout.pageHorizontal(context),
                8,
                ResponsiveLayout.pageHorizontal(context),
                16,
              ),
              children: [
                const Text(
                  '이미지에서 장소를 찾아드릴게요',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 10),
                const Text(
                  '랜드마크나 풍경이 잘 보이는 사진을 앨범에서 선택해 주세요.',
                  style: TextStyle(color: Color(0xFF6B7280)),
                ),
                const SizedBox(height: 24),
                AspectRatio(
                  aspectRatio: 1.05,
                  child: Container(
                    width: double.infinity,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(color: const Color(0xFFD8E1F7)),
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: _selectedImage == null
                        ? const Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.image_search_outlined,
                                color: AppColors.primary,
                                size: 56,
                              ),
                              SizedBox(height: 12),
                              Text(
                                '앨범에서 사진을 불러와 주세요',
                                style: TextStyle(color: Color(0xFF6B7280)),
                              ),
                            ],
                          )
                        : Image.file(
                            File(_selectedImage!.path),
                            fit: BoxFit.cover,
                          ),
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: OutlinedButton.icon(
                    onPressed: _picking ? null : _pickGalleryImage,
                    icon: const Icon(Icons.image_search_outlined),
                    label: Text(
                      _selectedImage == null ? '앨범에서 불러오기' : '다른 이미지 선택',
                    ),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.primary,
                      side: const BorderSide(color: AppColors.primary),
                    ),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: EdgeInsets.fromLTRB(ResponsiveLayout.pageHorizontal(context), 12, ResponsiveLayout.pageHorizontal(context), 20),
            child: SizedBox(
              width: double.infinity,
              height: 56,
              child: FilledButton(
                onPressed: _selectedImage == null || _picking
                    ? null
                    : _analyzeImage,
                child: Text(_picking ? '이미지를 불러오는 중' : '장소 분석하기'),
              ),
            ),
          ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    return widget.galleryOnly
        ? _buildGalleryScreen(context)
        : _buildCaptureScreen(context);
  }
}
