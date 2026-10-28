import 'package:flutter_test/flutter_test.dart';

import 'package:c_editor/main.dart';

void main() {
  testWidgets('app builds', (WidgetTester tester) async {
    await tester.pumpWidget(const CEditorApp());
    expect(find.byType(CEditorApp), findsOneWidget);
  });
}