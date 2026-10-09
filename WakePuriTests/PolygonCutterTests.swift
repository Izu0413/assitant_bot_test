import CoreGraphics
import XCTest
@testable import WakePuri

final class PolygonCutterTests: XCTestCase {
    private let accuracy: CGFloat = 0.001

    /// 100×100 の正方形(面積 10000)
    private let square: [CGPoint] = [
        CGPoint(x: 0, y: 0),
        CGPoint(x: 100, y: 0),
        CGPoint(x: 100, y: 100),
        CGPoint(x: 0, y: 100),
    ]

    func testAreaOfSquare() {
        XCTAssertEqual(PolygonCutter.area(of: square), 10000, accuracy: accuracy)
    }

    func testVerticalCutThroughMiddleMakesTwoHalves() throws {
        let pieces = try XCTUnwrap(
            PolygonCutter.split(square, from: CGPoint(x: 50, y: -10), to: CGPoint(x: 50, y: 110))
        )
        XCTAssertEqual(pieces.left.count, 4)
        XCTAssertEqual(pieces.right.count, 4)
        XCTAssertEqual(PolygonCutter.area(of: pieces.left), 5000, accuracy: accuracy)
        XCTAssertEqual(PolygonCutter.area(of: pieces.right), 5000, accuracy: accuracy)
    }

    func testDiagonalCutThroughCornersMakesTwoTriangles() throws {
        let pieces = try XCTUnwrap(
            PolygonCutter.split(square, from: CGPoint(x: -10, y: -10), to: CGPoint(x: 110, y: 110))
        )
        XCTAssertEqual(pieces.left.count, 3)
        XCTAssertEqual(pieces.right.count, 3)
        XCTAssertEqual(PolygonCutter.area(of: pieces.left), 5000, accuracy: accuracy)
        XCTAssertEqual(PolygonCutter.area(of: pieces.right), 5000, accuracy: accuracy)
    }

    func testStrokeEndingInsidePieceStillCutsAllTheWayThrough() throws {
        let pieces = try XCTUnwrap(
            PolygonCutter.split(square, from: CGPoint(x: 50, y: -10), to: CGPoint(x: 50, y: 30))
        )
        XCTAssertEqual(PolygonCutter.area(of: pieces.left), 5000, accuracy: accuracy)
        XCTAssertEqual(PolygonCutter.area(of: pieces.right), 5000, accuracy: accuracy)
    }

    func testStrokeBesidePieceDoesNotCut() {
        XCTAssertNil(PolygonCutter.split(square, from: CGPoint(x: 150, y: -10), to: CGPoint(x: 150, y: 110)))
    }

    func testStrokeWhoseExtensionCrossesPieceDoesNotCut() {
        // 線を延長すると正方形を通るが、なぞった範囲は正方形の下にある
        XCTAssertNil(PolygonCutter.split(square, from: CGPoint(x: 50, y: 120), to: CGPoint(x: 50, y: 200)))
    }

    func testStrokeAlongEdgeDoesNotCut() {
        XCTAssertNil(PolygonCutter.split(square, from: CGPoint(x: 0, y: -10), to: CGPoint(x: 0, y: 110)))
    }

    func testTinySliverIsNotCreated() {
        // 幅2の切れ端(面積200)は minimumPieceArea 未満
        XCTAssertNil(PolygonCutter.split(square, from: CGPoint(x: 2, y: -10), to: CGPoint(x: 2, y: 110)))
    }

    func testZeroLengthStrokeDoesNotCut() {
        XCTAssertNil(PolygonCutter.split(square, from: CGPoint(x: 50, y: 50), to: CGPoint(x: 50, y: 50)))
    }

    func testCuttingTwiceKeepsTotalArea() throws {
        let firstCut = try XCTUnwrap(
            PolygonCutter.split(square, from: CGPoint(x: 30, y: -10), to: CGPoint(x: 70, y: 110))
        )
        let secondCut = try XCTUnwrap(
            PolygonCutter.split(firstCut.left, from: CGPoint(x: -10, y: 40), to: CGPoint(x: 110, y: 60))
        )
        let totalArea = PolygonCutter.area(of: secondCut.left)
            + PolygonCutter.area(of: secondCut.right)
            + PolygonCutter.area(of: firstCut.right)
        XCTAssertEqual(totalArea, 10000, accuracy: accuracy)
    }
}
