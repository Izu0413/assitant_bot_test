import CoreGraphics

/// 紙片(凸多角形)を、指でなぞった直線で2つに分ける計算。
/// 長方形のシートを直線で切り続ける限り紙片は常に凸多角形なので、
/// 「各頂点が線のどちら側にあるか」で振り分けるだけで正しく分けられる。
enum PolygonCutter {
    /// これより小さい切れ端は作らない。線のなぞり損じで極小の紙片ができるのを防ぐ(シート座標でのpx²)
    static let minimumPieceArea: CGFloat = 400

    /// 浮動小数点の誤差で、線上にある点を左右どちらかに誤って振り分けないための許容距離(px)
    static let onLineTolerance: CGFloat = 0.5

    /// `start` から `end` へなぞった線で多角形を切る。
    /// なぞった範囲が多角形にかかっていれば、線を延長して多角形全体を切り分ける(ハサミをまっすぐ入れきるイメージ)。
    /// - Returns: 線の両側の多角形。切れない場合(線がかかっていない・端をなぞっただけ・切れ端が小さすぎる)は nil
    static func split(
        _ polygon: [CGPoint],
        from start: CGPoint,
        to end: CGPoint
    ) -> (left: [CGPoint], right: [CGPoint])? {
        let strokeX = end.x - start.x
        let strokeY = end.y - start.y
        let strokeLength = (strokeX * strokeX + strokeY * strokeY).squareRoot()
        guard strokeLength > 0, polygon.count >= 3 else { return nil }

        func signedDistance(_ point: CGPoint) -> CGFloat {
            let distance = (strokeX * (point.y - start.y) - strokeY * (point.x - start.x)) / strokeLength
            return abs(distance) < onLineTolerance ? 0 : distance
        }

        // なぞった線上での位置。0 が start、1 が end
        func positionAlongStroke(_ point: CGPoint) -> CGFloat {
            ((point.x - start.x) * strokeX + (point.y - start.y) * strokeY) / (strokeLength * strokeLength)
        }

        var left: [CGPoint] = []
        var right: [CGPoint] = []
        var pointsOnLine: [CGPoint] = []

        for index in polygon.indices {
            let current = polygon[index]
            let next = polygon[(index + 1) % polygon.count]
            let currentDistance = signedDistance(current)
            let nextDistance = signedDistance(next)

            if currentDistance >= 0 { left.append(current) }
            if currentDistance <= 0 { right.append(current) }
            if currentDistance == 0 { pointsOnLine.append(current) }

            let crossesLine = (currentDistance > 0 && nextDistance < 0) || (currentDistance < 0 && nextDistance > 0)
            if crossesLine {
                let ratio = currentDistance / (currentDistance - nextDistance)
                let crossing = CGPoint(
                    x: current.x + (next.x - current.x) * ratio,
                    y: current.y + (next.y - current.y) * ratio
                )
                left.append(crossing)
                right.append(crossing)
                pointsOnLine.append(crossing)
            }
        }

        guard area(of: left) >= minimumPieceArea, area(of: right) >= minimumPieceArea else { return nil }

        // 延長した線が多角形を横切っていても、なぞった範囲そのものが多角形にかかっていなければ切らない。
        // そうしないと、別の紙片を切ったつもりの線で離れた紙片まで切れてしまう。
        let cutPositions = pointsOnLine.map(positionAlongStroke)
        guard let cutStart = cutPositions.min(), let cutEnd = cutPositions.max() else { return nil }
        let overlapLength = (min(cutEnd, 1) - max(cutStart, 0)) * strokeLength
        guard overlapLength > onLineTolerance else { return nil }

        return (left, right)
    }

    /// 多角形の面積(靴ひも公式)。頂点の並びが時計回りでも反時計回りでも正の値を返す
    static func area(of polygon: [CGPoint]) -> CGFloat {
        guard polygon.count >= 3 else { return 0 }
        var twiceSignedArea: CGFloat = 0
        for index in polygon.indices {
            let current = polygon[index]
            let next = polygon[(index + 1) % polygon.count]
            twiceSignedArea += current.x * next.y - next.x * current.y
        }
        return abs(twiceSignedArea) / 2
    }
}
